# 数据结构

源数据未知值使用 JSON `null`，列表使用显式数组。示例均为虚构数据。

## Profile

- `graduation_year`: integer
- `education`: string or null
- `major`: string or null
- `preferred_role_categories`: list of strings
- `acceptable_role_categories`: list of strings
- `preferred_cities`: list of strings
- `acceptable_cities`: list of strings
- `skills`: list of strings
- `resume_evidence`: list of objects with `kind`, `text`, and `skills`
- `preferred_companies`: list of strings
- `preferred_industries`: list of strings
- `recruitment_types`: list of strings
- `written_test_preference`: one of `any`, `prefer`, or `avoid`
- `allow_graduation_mismatch`: optional boolean; only use after the user explicitly requests a graduation-year exception
- `strict_city_match`: optional boolean; only set to `true` when the user explicitly says to recommend only named cities

工作区 `profile.json` 使用以下完整结构：

```json
{
  "schema_version": 1,
  "profile": {
    "graduation_year": 2027,
    "education": "本科",
    "major": "软件工程",
    "preferred_role_categories": ["软件开发"],
    "acceptable_role_categories": ["测试", "数据"],
    "preferred_cities": ["上海"],
    "acceptable_cities": ["杭州", "南京"],
    "skills": ["Python", "SQL", "Git"],
    "resume_evidence": [
      {
        "kind": "项目",
        "text": "使用 Python 和 SQL 完成匿名课程项目的数据处理模块。",
        "skills": ["Python", "SQL"]
      }
    ],
    "preferred_companies": [],
    "preferred_industries": ["互联网"],
    "recruitment_types": ["秋招"],
    "written_test_preference": "any"
  },
  "resume_summary": {
    "education": ["软件工程本科，预计 2027 年毕业"],
    "skills": ["Python", "SQL", "Git"],
    "internships": [],
    "projects": ["匿名课程项目的数据处理模块"],
    "quantified_results": [],
    "unknowns": ["暂无实习信息"]
  }
}
```

搜索脚本使用 `profile` 对象本身作为 `--profile` 文件内容。调用前从工作区包装结构中提取该对象到临时 JSON 文件；不要把包装结构直接传给搜索脚本。

## Opportunity

- `opportunity_id`: stable string beginning with `opp_`
- `company`: source company string or null
- `roles_raw`: source role value or null
- `role_categories`: normalized string list
- `target_graduation_years`: integer list
- `recruitment_types`: normalized string list
- `locations_raw`: source location value or null
- `locations_normalized`: normalized city string list
- `company_categories`: normalized industry string list
- `written_test`: boolean or null
- `deadline_raw`: source deadline value or null
- `deadline_date`: ISO 8601 date string or null
- `updated_at`: ISO 8601 date string or source value or null
- `application_url`: URL string or null
- `announcement_url`: URL string or null
- `notes`: source notes string or null
- `verification_required`: boolean

## Search Result

- `generated_at`: ISO 8601 timestamp string
- `dataset_version`: string
- `valid_records`: integer
- `skipped_records`: integer
- `recommendations`: list of Recommendation objects

完整搜索输出示例：

```json
{
  "generated_at": "2026-07-22T08:00:00+00:00",
  "dataset_version": "campus-jobs-example",
  "valid_records": 11223,
  "skipped_records": 0,
  "recommendations": [
    {
      "opportunity": {
        "opportunity_id": "opp_example01",
        "company": "示例科技",
        "roles_raw": "软件开发工程师",
        "role_categories": ["软件开发"],
        "target_graduation_years": [2027],
        "recruitment_types": ["秋招"],
        "locations_raw": "上海、杭州",
        "locations_normalized": ["上海", "杭州"],
        "company_categories": ["互联网"],
        "written_test": true,
        "deadline_raw": "2026-07-29",
        "deadline_date": "2026-07-29",
        "updated_at": "2026-07-22",
        "application_url": "https://example.com/apply",
        "announcement_url": "https://example.com/campus",
        "notes": "",
        "verification_required": true
      },
      "score": 90,
      "tier": "高度匹配",
      "urgency": "本周处理",
      "matched_role_category": "软件开发",
      "matched_city": "上海",
      "score_breakdown": {
        "role": 30,
        "evidence": 25,
        "city": 15,
        "major": 15,
        "company": 5,
        "conditions": 0
      },
      "reasons": ["岗位方向匹配：软件开发", "城市匹配：上海"],
      "gaps": ["源数据标记为需要人工确认"],
      "graduation_filter_relaxed": false
    }
  ]
}
```

## Recommendation

- `opportunity`: Opportunity object
- `score`: integer
- `tier`: string
- `urgency`: string
- `matched_role_category`: string or null
- `matched_city`: string or null
- `score_breakdown`: object mapping score dimension to integer points
- `reasons`: list of grounded strings
- `gaps`: list of verification or evidence gaps
- `graduation_filter_relaxed`: boolean indicating the user explicitly relaxed only the graduation-year filter

## Application

- `opportunity_id`: stable opportunity ID
- `company`: company string or empty string
- `roles_raw`: source role string or empty string
- `status`: one of `待评估`, `待投递`, `已投递`, `笔试`, `面试`, `淘汰`, or `Offer`
- `added_at`: ISO 8601 timestamp string
- `updated_at`: ISO 8601 timestamp string
- `notes`: user-owned text or empty string
- `application_url`: URL string or empty string
- `announcement_url`: URL string or empty string

`applications.csv` 的列顺序固定：

```csv
opportunity_id,company,roles_raw,status,added_at,updated_at,notes,application_url,announcement_url
opp_example01,示例科技,软件开发工程师,待投递,2026-07-22T08:00:00+00:00,2026-07-22T08:00:00+00:00,先核实笔试安排,https://example.com/apply,https://example.com/campus
```

`revision` 不存入 CSV。`list` 返回当前文件原始字节的 SHA-256 十六进制字符串；每次 `add` 或 `update` 都必须提交刚读取的 `expected_revision`。
