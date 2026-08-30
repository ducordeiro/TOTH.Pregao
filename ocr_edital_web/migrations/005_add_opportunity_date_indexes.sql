CREATE INDEX IF NOT EXISTS idx_opportunities_published_at
  ON opportunities(published_at, radar_status, modality_code, uf);

CREATE INDEX IF NOT EXISTS idx_opportunities_proposal_start
  ON opportunities(proposal_start_at, radar_status, modality_code, uf);
