"""Create a small deterministic database for local end-to-end checks."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server
from etl.models import MatchResult, NormalizedOpportunity, OpportunityItem
from etl.repository import ETLRepository


def main() -> None:
    server.init_database()
    repository = ETLRepository(server.DATABASE_PATH)
    repository.initialize()
    run_id = repository.create_run("pncp", "e2e_fixture", {"fixture": True})
    today = date.today()

    opportunities = [
        NormalizedOpportunity(
            external_key="pncp:12345678000195:2026:1",
            source="pncp",
            title="Aquisição de cadeiras ergonômicas",
            pncp_control_number="12345678000195-1-000001/2026",
            source_cnpj="12345678000195",
            year=2026,
            sequence=1,
            process_number="PE 001/2026",
            description="Aquisição de cadeiras e mobiliário para escritório.",
            buyer_name="Prefeitura Municipal de Teste",
            buyer_cnpj="12345678000195",
            uf="RS",
            city="Porto Alegre",
            modality="Pregão - Eletrônico",
            modality_code=6,
            status="Recebendo propostas",
            estimated_value=42000.0,
            published_at=today.isoformat(),
            proposal_end_at=(today + timedelta(days=7)).isoformat(),
            source_url="https://pncp.gov.br/app/editais/12345678000195/2026/1",
            detail_url="https://pncp.gov.br/app/editais/12345678000195/2026/1",
            items=[
                OpportunityItem(
                    source_item_id="1",
                    item_number="1",
                    title="Cadeira ergonômica",
                    description="Cadeira giratória com apoio lombar.",
                    quantity=20,
                    unit="UND",
                    estimated_unit_value=1200.0,
                    estimated_total_value=24000.0,
                ),
                OpportunityItem(
                    source_item_id="2",
                    item_number="2",
                    title="Mesa de escritório",
                    description="Mesa retangular em MDF.",
                    quantity=10,
                    unit="UND",
                    estimated_unit_value=1800.0,
                    estimated_total_value=18000.0,
                ),
            ],
        ),
        NormalizedOpportunity(
            external_key="pncp:12345678000195:2026:2",
            source="pncp",
            title="Contratação de manutenção predial",
            pncp_control_number="12345678000195-1-000002/2026",
            source_cnpj="12345678000195",
            year=2026,
            sequence=2,
            process_number="DL 002/2026",
            description="Serviços de manutenção preventiva e corretiva.",
            buyer_name="Prefeitura Municipal de Teste",
            buyer_cnpj="12345678000195",
            uf="RS",
            city="Canoas",
            modality="Dispensa",
            modality_code=8,
            status="Divulgada",
            estimated_value=15000.0,
            published_at=today.isoformat(),
            proposal_end_at=None,
            source_url="https://pncp.gov.br/app/editais/12345678000195/2026/2",
            detail_url="https://pncp.gov.br/app/editais/12345678000195/2026/2",
        ),
    ]

    counters = {"fetched": 0, "inserted": 0, "updated": 0, "skipped": 0, "failed": 0}
    for opportunity in opportunities:
        outcome, _ = repository.persist_record(
            run_id=run_id,
            source_endpoint="e2e_fixture",
            request_url=opportunity.source_url or "",
            raw_payload=opportunity.to_dict(),
            opportunity=opportunity,
            match=MatchResult(score=85, matched_keywords=["teste"]),
        )
        counters["fetched"] += 1
        counters[outcome] += 1
    repository.finish_run(run_id, status="success", counters=counters)

    server.import_business(
        {
            "pncp_link": "https://pncp.gov.br/app/editais/12345678000195/2026/1",
            "empresa": "Empresa de Teste",
            "oportunidade": {
                "objeto": "Aquisição de cadeiras ergonômicas",
                "orgao": "Prefeitura Municipal de Teste",
                "municipio": "Porto Alegre",
                "uf": "RS",
                "modalidade": "Pregão - Eletrônico",
                "processo": "PE 001/2026",
                "encerramento": (today + timedelta(days=7)).isoformat(),
                "situacao": "Recebendo propostas",
            },
            "itens": [
                {
                    "numero": "1",
                    "lote": "1",
                    "descricao": "Cadeira ergonômica",
                    "quantidade": "20",
                    "unidade": "UND",
                    "valor_unitario_estimado": 1200,
                    "valor_total_estimado": 24000,
                    "criterio_julgamento": "Menor preço",
                    "situacao": "Aberto",
                }
            ],
        }
    )
    print(server.DATABASE_PATH)


if __name__ == "__main__":
    main()
