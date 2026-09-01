CREATE TABLE IF NOT EXISTS opportunity_object_classifications (
  opportunity_id TEXT PRIMARY KEY
    REFERENCES opportunities(id) ON DELETE CASCADE,
  opportunity_type TEXT NOT NULL DEFAULT 'unclassified'
    CHECK (opportunity_type IN ('material', 'servico', 'unclassified')),
  has_material INTEGER NOT NULL DEFAULT 0 CHECK (has_material IN (0, 1)),
  has_service INTEGER NOT NULL DEFAULT 0 CHECK (has_service IN (0, 1)),
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_opportunity_object_class_type
  ON opportunity_object_classifications(opportunity_type, opportunity_id);

CREATE INDEX IF NOT EXISTS idx_opportunity_object_class_material
  ON opportunity_object_classifications(has_material, opportunity_id)
  WHERE has_material = 1;

CREATE INDEX IF NOT EXISTS idx_opportunity_object_class_service
  ON opportunity_object_classifications(has_service, opportunity_id)
  WHERE has_service = 1;

WITH item_types AS (
  SELECT
    opportunity_id,
    MAX(
      CASE WHEN classify_object_text(
        COALESCE(title, '') || ' ' || COALESCE(description, '')
      ) = 'material' THEN 1 ELSE 0 END
    ) AS has_material,
    MAX(
      CASE WHEN classify_object_text(
        COALESCE(title, '') || ' ' || COALESCE(description, '')
      ) = 'servico' THEN 1 ELSE 0 END
    ) AS has_service
  FROM opportunity_items
  GROUP BY opportunity_id
)
INSERT INTO opportunity_object_classifications (
  opportunity_id, opportunity_type, has_material, has_service, updated_at
)
SELECT
  o.id,
  COALESCE(
    NULLIF(classify_object_text(
      COALESCE(o.title, '') || ' ' || COALESCE(o.description, '')
    ), ''),
    'unclassified'
  ),
  COALESCE(item_types.has_material, 0),
  COALESCE(item_types.has_service, 0),
  o.updated_at
FROM opportunities o
LEFT JOIN item_types ON item_types.opportunity_id = o.id
WHERE NOT EXISTS (
  SELECT 1
  FROM opportunity_object_classifications classification
  WHERE classification.opportunity_id = o.id
);
