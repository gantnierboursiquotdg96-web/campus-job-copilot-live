"""Read a complete live Feishu Base snapshot before every recommendation. No cache fallback."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid
from datetime import date, datetime, timezone, timedelta

from search_opportunities import load_dataset, search

SKILL = Path(__file__).resolve().parents[1]
TZ = timezone(timedelta(hours=8))

def text(value):
    if isinstance(value, list):
        return ' / '.join(str(v) for v in value)
    return '' if value is None else str(value)

def url(value):
    # Preserve a single source URL; do not invent links from prose.
    value = text(value)
    links = re.findall(r'https?://[^\s<>\[\]()]+', value)
    unique = list(dict.fromkeys(links))
    return unique[0].rstrip('。，；') if len(unique) == 1 else None

def full_date(value):
    raw = text(value).strip()
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}T.*', raw):
        try:
            return datetime.fromisoformat(raw.replace('Z', '+00:00')).astimezone(TZ).date().isoformat()
        except ValueError:
            return None
    match = re.fullmatch(r'(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})日?', raw)
    if match:
        try:
            return date(*map(int, match.groups())).isoformat()
        except ValueError:
            pass
    return None  # No inferred year for 10.31, ASAP, or until filled.

def roles(value):
    raw = text(value)
    patterns = {
      '软件开发':r'软件开发|前端|后端|服务端|Java|Golang|程序员',
      '数据':r'数据分析|数据科学|数据开发|数据工程|商业分析',
      '测试':r'软件测试|测试开发|自动化测试', '运维':r'运维',
      '芯片设计':r'芯片设计|数字IC|模拟IC|集成电路设计',
      '硬件研发':r'硬件|电路设计|电子研发', '嵌入式':r'嵌入式|单片机|固件',
      '产品':r'产品经理|产品助理|产品管理|产品策划',
      '运营':r'运营', '市场营销':r'市场|营销|品牌|推广',
      '销售':r'销售|商务拓展|客户经理', '职能':r'职能|人力|财务|会计|行政|管培'
    }
    return [category for category, pattern in patterns.items() if re.search(pattern, raw, re.I)]

def convert(row, columns, config):
    # Resolve stable field IDs to the current display names returned in the manifest.
    names = {v['field_id']: k for k,v in columns.items() if 'field_id' in v}
    absent = set(config['fields'].values()) - names.keys()
    if absent:
        raise RuntimeError('Required fields missing or inaccessible: ' + ','.join(sorted(absent)))
    def get(key): return row.get(names[config['fields'][key]])
    raw_cities = text(get('cities'))
    cities = list(dict.fromkeys(part.strip() for part in re.split(r'[/、,，;；\s]+',raw_cities) if part.strip()))
    raw_industry = text(get('industry'))
    industries = [part for part in re.split(r'[/、,，;；\s]+',raw_industry) if part]
    for cat, pattern in {'电商':r'电商|电子商务','消费品':r'快消|消费品|食品|饮料|美妆|日化','零售':r'零售','互联网':r'互联网','游戏':r'游戏','金融':r'金融|银行|证券','制造':r'制造'}.items():
        if re.search(pattern,raw_industry) and cat not in industries: industries.append(cat)
    raw_test = text(get('test'))
    written = True if raw_test == '需要笔试' else False if raw_test == '含免笔试' else None
    # "含免笔试" means some roles are exempt, not necessarily this applicant's role.
    if raw_test == '含免笔试': written = None
    years = sorted(set(map(int,re.findall(r'20\d{2}',text(get('years'))))))
    recruitment_raw = text(get('recruitment'))
    recruitment = [v for v in ['秋招','春招','实习','补录'] if v in recruitment_raw]
    record_id = row.get('record_id')
    if not isinstance(record_id,str) or not record_id:
        raise RuntimeError('Missing record_id')
    return {
      'opportunity_id':'opp_'+hashlib.sha256((config['base_token']+'/'+config['table_id']+'/'+record_id).encode()).hexdigest()[:16],
      'source_record_id':record_id,'source_url':f"https://rcn1ey8vkhdz.feishu.cn/base/{config['base_token']}?table={config['table_id']}&record={record_id}",
      'company':text(get('company')) or None,'roles_raw':text(get('roles')) or None,'role_categories':roles(get('roles')),
      'target_graduation_years':years,'recruitment_types':recruitment,
      'locations_raw':raw_cities or None,'locations_normalized':cities,'company_categories':industries,
      'written_test':written,'written_test_raw':raw_test or None,
      'deadline_raw':text(get('deadline')) or None,'deadline_date':full_date(get('deadline')),
      'updated_at':full_date(get('updated')),
      'application_url':url(get('application')),'announcement_url':url(get('announcement')),
      'application_raw':get('application'),'announcement_raw':get('announcement'),
      'notes':text(get('notes')) or None,'verification_required':True
    }

def cli(executable, arguments, cwd):
    env = os.environ.copy()
    env['LARKSUITE_CLI_NO_UPDATE_NOTIFIER']='1'
    env['LARKSUITE_CLI_NO_SKILLS_NOTIFIER']='1'
    proc = subprocess.run([executable,*arguments],cwd=cwd,env=env,capture_output=True,encoding='utf-8',timeout=180)
    if proc.returncode:
        # Do not print command output, which may contain user identity or credentials.
        raise RuntimeError(f'Feishu read failed (exit {proc.returncode}). Check login, app scopes and source reading permission; no old data used.')
    return proc.stdout

def snapshot(executable, workspace, config):
    folder=workspace/'live-data'/('read-'+uuid.uuid4().hex)
    folder.mkdir(parents=True)
    offset=0; version=None; context=None; records=[]; seen=set(); page=0
    while True:
        relative=folder.relative_to(workspace)/f'page-{page}.ndjson'
        args=['base','+record-list','--base-token',config['base_token'],'--table-id',config['table_id'],
              '--as','user','--format','ndjson','--limit','2000','--offset',str(offset),'--output',str(relative)]
        for field in config['fields'].values(): args.extend(['--field-id',field])
        print(f'Reading live Base page {page+1}...',file=sys.stderr,flush=True)
        cli(executable,args,workspace)
        output=workspace/relative
        manifest=json.loads(output.with_suffix('.manifest.json').read_text(encoding='utf-8'))
        if manifest['base_token']!=config['base_token'] or manifest['table_id']!=config['table_id']:
            raise RuntimeError('Source identity mismatch')
        if manifest.get('rev') is None or manifest.get('query_context',{}).get('record_scope')!='all_records':
            raise RuntimeError('Unverifiable version or unexpected query scope')
        if page==0: version=manifest['rev']; context=manifest['query_context']
        if manifest['rev']!=version or manifest['query_context']!=context:
            raise RuntimeError('Database changed during pagination; rerun from the first page. No partial recommendation produced.')
        rows=[json.loads(line) for line in output.read_text(encoding='utf-8').splitlines() if line.strip()]
        if len(rows)!=manifest['records_count']: raise RuntimeError('Page count mismatch')
        for row in rows:
            rec=convert(row,manifest['columns'],config)
            if rec['source_record_id'] in seen: raise RuntimeError('Duplicate record across pages')
            seen.add(rec['source_record_id']); records.append(rec)
        if manifest.get('has_more') is False: break
        if manifest.get('has_more') is not True: raise RuntimeError('Missing pagination completion signal')
        new=manifest.get('next_offset')
        if not isinstance(new,int) or new<=offset: raise RuntimeError('Invalid next_offset')
        offset=new; page+=1
        if page>100: raise RuntimeError('Unexpected pagination size')
    # Verify the current table count and revision after the final page.
    envelope=json.loads(cli(executable,['base','+table-list','--base-token',config['base_token'],'--as','user'],workspace))
    if envelope.get('ok') is not True: raise RuntimeError('Final source verification failed')
    table=next((t for t in envelope['data']['tables'] if t['id']==config['table_id']),None)
    if not table or table.get('rev')!=version or table.get('records_count')!=len(records):
        raise RuntimeError('Source count or revision changed; rerun. No partial recommendation produced.')
    if not records: raise RuntimeError('Empty database; no old data used')
    dataset=folder/'opportunities.jsonl'
    dataset.write_text(''.join(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n' for r in records),encoding='utf-8')
    now=datetime.now(TZ)
    info={'schema_version':1,'dataset_version':f"live-{config['table_id']}-rev-{version}",
          'record_count':len(records),'sha256':hashlib.sha256(dataset.read_bytes()).hexdigest(),
          'snapshot_date':now.date().isoformat(),'fetched_at':now.isoformat(),
          'source':config,'source_revision':version,'complete':True,'pages':page+1,
          'latest_record_updated_at':max((r['updated_at'] for r in records if r['updated_at']),default=None)}
    manifest_path=folder/'data-manifest.json'
    manifest_path.write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
    return dataset,manifest_path,info

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace',type=Path,required=True)
    parser.add_argument('--profile',type=Path,required=True,help='Unwrapped profile JSON')
    parser.add_argument('--today',default=datetime.now(TZ).date().isoformat())
    parser.add_argument('--limit',type=int,default=15)
    parser.add_argument('--cli',default='lark-cli',help='CLI executable or command path')
    args=parser.parse_args()
    try:
        profile=json.loads(args.profile.resolve().read_text(encoding='utf-8-sig'))
        if not isinstance(profile.get('graduation_year'),int): raise ValueError('profile.graduation_year is required')
        today=date.fromisoformat(args.today)
        executable=shutil.which(args.cli)
        if not executable: raise RuntimeError('Install lark-cli and restart your terminal first')
        workspace=args.workspace.resolve(); workspace.mkdir(parents=True,exist_ok=True)
        config=json.loads((SKILL/'assets/live-source.json').read_text(encoding='utf-8'))
        dataset,manifest,info=snapshot(executable,workspace,config)
        rows,skipped,validated=load_dataset(dataset,manifest)
        taxonomy=json.loads((SKILL/'assets/matching-taxonomy.json').read_text(encoding='utf-8'))
        recommendations=search(profile,rows,taxonomy,today,limit=args.limit)
        for recommendation in recommendations:
            recommendation['gaps'].append('分类匹配不代表具体JD资格；多岗位记录不证明该岗位对应匹配城市。')
        result={'generated_at':datetime.now(TZ).isoformat(),'dataset_version':info['dataset_version'],
                'fetched_at':info['fetched_at'],'source_revision':info['source_revision'],
                'source_url':config['url'],'record_scope':'all_records','complete':True,
                'valid_records':len(rows),'skipped_records':skipped,
                'latest_record_updated_at':info['latest_record_updated_at'],
                'recommendations':recommendations}
        reports=workspace/'reports'; reports.mkdir(exist_ok=True)
        path=reports/('live-recommendations-'+uuid.uuid4().hex+'.json')
        path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        result['report_file']=str(path)
        print(json.dumps(result,ensure_ascii=False))
        return 0
    except (OSError,ValueError,KeyError,RuntimeError,subprocess.TimeoutExpired) as exc:
        print(f'Live recommendation stopped: {exc}',file=sys.stderr)
        return 2

if __name__=='__main__': sys.exit(main())
