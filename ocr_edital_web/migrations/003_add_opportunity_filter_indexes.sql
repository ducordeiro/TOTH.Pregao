CREATE INDEX IF NOT EXISTS idx_opportunities_proposal_end
  ON opportunities(proposal_end_at, radar_status, modality_code, uf);

CREATE INDEX IF NOT EXISTS idx_opportunities_missing_end_published
  ON opportunities(published_at, radar_status, modality_code, uf)
  WHERE proposal_end_at IS NULL OR proposal_end_at = '';
