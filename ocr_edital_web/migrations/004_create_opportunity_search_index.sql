CREATE VIRTUAL TABLE IF NOT EXISTS opportunity_search USING fts5(
  opportunity_id UNINDEXED,
  content,
  tokenize = 'unicode61 remove_diacritics 2'
);

INSERT INTO opportunity_search(rowid, opportunity_id, content)
SELECT
  o.rowid,
  o.id,
  TRIM(
    COALESCE(o.title, '') || ' ' || COALESCE(o.description, '') || ' ' ||
    COALESCE(o.buyer_name, '') || ' ' || COALESCE(o.city, '') || ' ' ||
    COALESCE(o.modality, '') || ' ' || COALESCE(o.process_number, '') || ' ' ||
    COALESCE(o.pncp_control_number, '') || ' ' || COALESCE(o.uasg, '') || ' ' ||
    COALESCE(o.status, '') || ' ' ||
    COALESCE((
      SELECT GROUP_CONCAT(
        COALESCE(oi.source_item_id, '') || ' ' || COALESCE(oi.lot_number, '') || ' ' ||
        COALESCE(oi.item_number, '') || ' ' || COALESCE(oi.title, '') || ' ' ||
        COALESCE(oi.description, '') || ' ' || COALESCE(oi.technical_object, '') || ' ' ||
        COALESCE(oi.unit, '') || ' ' || COALESCE(oi.status, ''),
        ' '
      ) FROM opportunity_items oi WHERE oi.opportunity_id = o.id
    ), '') || ' ' ||
    COALESCE((
      SELECT GROUP_CONCAT(
        COALESCE(od.document_type, '') || ' ' || COALESCE(od.title, '') || ' ' ||
        COALESCE(od.filename, ''),
        ' '
      ) FROM opportunity_documents od WHERE od.opportunity_id = o.id
    ), '')
  )
FROM opportunities o
WHERE NOT EXISTS (
  SELECT 1 FROM opportunity_search LIMIT 1
);

CREATE TRIGGER IF NOT EXISTS opportunities_search_ai AFTER INSERT ON opportunities BEGIN
  INSERT OR REPLACE INTO opportunity_search(rowid, opportunity_id, content)
  VALUES (
    NEW.rowid,
    NEW.id,
    TRIM(
      COALESCE(NEW.title, '') || ' ' || COALESCE(NEW.description, '') || ' ' ||
      COALESCE(NEW.buyer_name, '') || ' ' || COALESCE(NEW.city, '') || ' ' ||
      COALESCE(NEW.modality, '') || ' ' || COALESCE(NEW.process_number, '') || ' ' ||
      COALESCE(NEW.pncp_control_number, '') || ' ' || COALESCE(NEW.uasg, '') || ' ' ||
      COALESCE(NEW.status, '')
    )
  );
END;

CREATE TRIGGER IF NOT EXISTS opportunities_search_au AFTER UPDATE ON opportunities BEGIN
  DELETE FROM opportunity_search WHERE rowid = OLD.rowid;
  INSERT INTO opportunity_search(rowid, opportunity_id, content)
  SELECT
    o.rowid,
    o.id,
    TRIM(
      COALESCE(o.title, '') || ' ' || COALESCE(o.description, '') || ' ' ||
      COALESCE(o.buyer_name, '') || ' ' || COALESCE(o.city, '') || ' ' ||
      COALESCE(o.modality, '') || ' ' || COALESCE(o.process_number, '') || ' ' ||
      COALESCE(o.pncp_control_number, '') || ' ' || COALESCE(o.uasg, '') || ' ' ||
      COALESCE(o.status, '') || ' ' ||
      COALESCE((SELECT GROUP_CONCAT(COALESCE(oi.source_item_id, '') || ' ' || COALESCE(oi.lot_number, '') || ' ' || COALESCE(oi.item_number, '') || ' ' || COALESCE(oi.title, '') || ' ' || COALESCE(oi.description, '') || ' ' || COALESCE(oi.technical_object, '') || ' ' || COALESCE(oi.unit, '') || ' ' || COALESCE(oi.status, ''), ' ') FROM opportunity_items oi WHERE oi.opportunity_id = o.id), '') || ' ' ||
      COALESCE((SELECT GROUP_CONCAT(COALESCE(od.document_type, '') || ' ' || COALESCE(od.title, '') || ' ' || COALESCE(od.filename, ''), ' ') FROM opportunity_documents od WHERE od.opportunity_id = o.id), '')
    )
  FROM opportunities o WHERE o.id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS opportunities_search_ad AFTER DELETE ON opportunities BEGIN
  DELETE FROM opportunity_search WHERE rowid = OLD.rowid;
END;

CREATE TRIGGER IF NOT EXISTS opportunity_items_search_ai AFTER INSERT ON opportunity_items BEGIN
  DELETE FROM opportunity_search WHERE rowid = (SELECT rowid FROM opportunities WHERE id = NEW.opportunity_id);
  INSERT INTO opportunity_search(rowid, opportunity_id, content)
  SELECT o.rowid, o.id,
    TRIM(COALESCE(o.title, '') || ' ' || COALESCE(o.description, '') || ' ' || COALESCE(o.buyer_name, '') || ' ' || COALESCE(o.city, '') || ' ' || COALESCE(o.modality, '') || ' ' || COALESCE(o.process_number, '') || ' ' || COALESCE(o.pncp_control_number, '') || ' ' || COALESCE(o.uasg, '') || ' ' || COALESCE(o.status, '') || ' ' || COALESCE((SELECT GROUP_CONCAT(COALESCE(oi.source_item_id, '') || ' ' || COALESCE(oi.lot_number, '') || ' ' || COALESCE(oi.item_number, '') || ' ' || COALESCE(oi.title, '') || ' ' || COALESCE(oi.description, '') || ' ' || COALESCE(oi.technical_object, '') || ' ' || COALESCE(oi.unit, '') || ' ' || COALESCE(oi.status, ''), ' ') FROM opportunity_items oi WHERE oi.opportunity_id = o.id), '') || ' ' || COALESCE((SELECT GROUP_CONCAT(COALESCE(od.document_type, '') || ' ' || COALESCE(od.title, '') || ' ' || COALESCE(od.filename, ''), ' ') FROM opportunity_documents od WHERE od.opportunity_id = o.id), ''))
  FROM opportunities o WHERE o.id = NEW.opportunity_id;
END;

CREATE TRIGGER IF NOT EXISTS opportunity_items_search_au AFTER UPDATE ON opportunity_items BEGIN
  DELETE FROM opportunity_search WHERE rowid = (SELECT rowid FROM opportunities WHERE id = NEW.opportunity_id);
  INSERT INTO opportunity_search(rowid, opportunity_id, content)
  SELECT o.rowid, o.id,
    TRIM(COALESCE(o.title, '') || ' ' || COALESCE(o.description, '') || ' ' || COALESCE(o.buyer_name, '') || ' ' || COALESCE(o.city, '') || ' ' || COALESCE(o.modality, '') || ' ' || COALESCE(o.process_number, '') || ' ' || COALESCE(o.pncp_control_number, '') || ' ' || COALESCE(o.uasg, '') || ' ' || COALESCE(o.status, '') || ' ' || COALESCE((SELECT GROUP_CONCAT(COALESCE(oi.source_item_id, '') || ' ' || COALESCE(oi.lot_number, '') || ' ' || COALESCE(oi.item_number, '') || ' ' || COALESCE(oi.title, '') || ' ' || COALESCE(oi.description, '') || ' ' || COALESCE(oi.technical_object, '') || ' ' || COALESCE(oi.unit, '') || ' ' || COALESCE(oi.status, ''), ' ') FROM opportunity_items oi WHERE oi.opportunity_id = o.id), '') || ' ' || COALESCE((SELECT GROUP_CONCAT(COALESCE(od.document_type, '') || ' ' || COALESCE(od.title, '') || ' ' || COALESCE(od.filename, ''), ' ') FROM opportunity_documents od WHERE od.opportunity_id = o.id), ''))
  FROM opportunities o WHERE o.id = NEW.opportunity_id;
END;

CREATE TRIGGER IF NOT EXISTS opportunity_items_search_ad AFTER DELETE ON opportunity_items BEGIN
  DELETE FROM opportunity_search WHERE rowid = (SELECT rowid FROM opportunities WHERE id = OLD.opportunity_id);
  INSERT INTO opportunity_search(rowid, opportunity_id, content)
  SELECT o.rowid, o.id,
    TRIM(COALESCE(o.title, '') || ' ' || COALESCE(o.description, '') || ' ' || COALESCE(o.buyer_name, '') || ' ' || COALESCE(o.city, '') || ' ' || COALESCE(o.modality, '') || ' ' || COALESCE(o.process_number, '') || ' ' || COALESCE(o.pncp_control_number, '') || ' ' || COALESCE(o.uasg, '') || ' ' || COALESCE(o.status, '') || ' ' || COALESCE((SELECT GROUP_CONCAT(COALESCE(oi.source_item_id, '') || ' ' || COALESCE(oi.lot_number, '') || ' ' || COALESCE(oi.item_number, '') || ' ' || COALESCE(oi.title, '') || ' ' || COALESCE(oi.description, '') || ' ' || COALESCE(oi.technical_object, '') || ' ' || COALESCE(oi.unit, '') || ' ' || COALESCE(oi.status, ''), ' ') FROM opportunity_items oi WHERE oi.opportunity_id = o.id), '') || ' ' || COALESCE((SELECT GROUP_CONCAT(COALESCE(od.document_type, '') || ' ' || COALESCE(od.title, '') || ' ' || COALESCE(od.filename, ''), ' ') FROM opportunity_documents od WHERE od.opportunity_id = o.id), ''))
  FROM opportunities o WHERE o.id = OLD.opportunity_id;
END;

CREATE TRIGGER IF NOT EXISTS opportunity_documents_search_ai AFTER INSERT ON opportunity_documents BEGIN
  UPDATE opportunities SET updated_at = updated_at WHERE id = NEW.opportunity_id;
END;

CREATE TRIGGER IF NOT EXISTS opportunity_documents_search_au AFTER UPDATE ON opportunity_documents BEGIN
  UPDATE opportunities SET updated_at = updated_at WHERE id = NEW.opportunity_id;
END;

CREATE TRIGGER IF NOT EXISTS opportunity_documents_search_ad AFTER DELETE ON opportunity_documents BEGIN
  UPDATE opportunities SET updated_at = updated_at WHERE id = OLD.opportunity_id;
END;
