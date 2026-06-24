from __future__ import annotations

import json

from sqlalchemy import text
from sqlalchemy.sql.elements import TextClause

from app.ai.layout_v2.material_retrieval_plan import MaterialRetrievalGroup


MATERIAL_SEARCH_TEXT = """LOWER(CONCAT_WS(' ',
    COALESCE(m.meta_info ->> 'display_name', ''),
    COALESCE(m.meta_info ->> 'filename', ''),
    COALESCE(m.meta_info ->> 'category', ''),
    COALESCE(m.meta_info ->> 'sub_category', ''),
    COALESCE(m.meta_info ->> 'detected_text', ''),
    COALESCE(m.meta_info ->> 'semantic_tags', ''),
    COALESCE(m.meta_info ->> 'subjects', ''),
    COALESCE(m.meta_info ->> 'objects', '')
))"""


def compile_material_plan_to_sql(
    group: MaterialRetrievalGroup,
    user_id: str | None,
) -> tuple[TextClause, dict]:
    sql = text(
        f"""
        SELECT m.*
        FROM materials AS m
        WHERE EXISTS (
            SELECT 1 FROM jsonb_array_elements_text(CAST(:material_types_json AS jsonb)) AS item(value)
            WHERE m.material_type = item.value
        )
          AND COALESCE(m.meta_info ->> 'annotation_version', '') = 'v2'
          AND COALESCE(m.meta_info ->> 'semantic_blocked', 'false') <> 'true'
          AND (
                COALESCE(m.meta_info ->> 'visibility', 'public') <> 'private'
                OR m.meta_info ->> 'owner_user_id' IS NULL
                OR m.meta_info ->> 'owner_user_id' = :user_id
          )
          AND EXISTS (
              SELECT 1 FROM jsonb_array_elements_text(CAST(:suggested_roles_json AS jsonb)) AS item(value)
              WHERE m.meta_info ->> 'suggested_role' = item.value
          )
          AND (
              :categories_empty
              OR EXISTS (
                  SELECT 1 FROM jsonb_array_elements_text(CAST(:categories_json AS jsonb)) AS item(value)
                  WHERE m.meta_info ->> 'category' = item.value
              )
          )
          AND (
              :density_empty
              OR EXISTS (
                  SELECT 1 FROM jsonb_array_elements_text(CAST(:density_json AS jsonb)) AS item(value)
                  WHERE m.meta_info ->> 'density' = item.value
              )
          )
          AND (
              NOT :background_safe
              OR COALESCE(m.meta_info ->> 'background_safe', 'false') = 'true'
          )
          AND NOT EXISTS (
              SELECT 1
              FROM jsonb_array_elements_text(COALESCE(CAST(m.meta_info AS jsonb) -> 'risk_flags', '[]'::jsonb)) AS risk(value)
              WHERE EXISTS (
                  SELECT 1 FROM jsonb_array_elements_text(CAST(:exclude_risks_json AS jsonb)) AS excluded(value)
                  WHERE excluded.value = risk.value
              )
          )
        ORDER BY
          CASE WHEN EXISTS (
              SELECT 1 FROM jsonb_array_elements_text(CAST(:sub_categories_json AS jsonb)) AS item(value)
              WHERE m.meta_info ->> 'sub_category' = item.value
          ) THEN 30 ELSE 0 END DESC,
          CASE WHEN EXISTS (
              SELECT 1 FROM jsonb_array_elements_text(CAST(:query_terms_json AS jsonb)) AS item(value)
              WHERE {MATERIAL_SEARCH_TEXT} LIKE '%' || LOWER(item.value) || '%'
          ) THEN 20 ELSE 0 END DESC,
          CASE WHEN EXISTS (
              SELECT 1 FROM jsonb_array_elements_text(CAST(:styles_json AS jsonb)) AS item(value)
              WHERE COALESCE(CAST(m.style_tags AS jsonb), '[]'::jsonb) ? item.value
                 OR LOWER(COALESCE(m.meta_info ->> 'visual_style', '')) = LOWER(item.value)
                 OR LOWER(COALESCE(m.meta_info ->> 'color_tone', '')) = LOWER(item.value)
          ) THEN 10 ELSE 0 END DESC,
          m.updated_at DESC,
          m.id
        LIMIT :pool_limit
        """
    )
    params = {
        "material_types_json": json.dumps(group.material_types, ensure_ascii=False),
        "suggested_roles_json": json.dumps(group.suggested_roles, ensure_ascii=False),
        "categories_json": json.dumps(group.categories, ensure_ascii=False),
        "categories_empty": not group.categories,
        "sub_categories_json": json.dumps(group.sub_categories, ensure_ascii=False),
        "styles_json": json.dumps(group.styles, ensure_ascii=False),
        "query_terms_json": json.dumps(group.query_terms, ensure_ascii=False),
        "exclude_risks_json": json.dumps(group.exclude_risks, ensure_ascii=False),
        "density_json": json.dumps(group.density, ensure_ascii=False),
        "density_empty": not group.density,
        "background_safe": group.background_safe,
        "user_id": str(user_id or ""),
        "pool_limit": min(60, max(group.limit, group.limit * 3)),
    }
    return sql, params
