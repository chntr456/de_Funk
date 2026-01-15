#!/usr/bin/env python3
"""
Test Chicago/Cook County Ingestion.

Runs bulk ingestion for Chicago and Cook County providers using dev profile settings.
Run via spark-submit for cluster execution.

Usage:
    ./scripts/spark-cluster/submit-job.sh scripts/ingest/test_chicago_ingestion.py
    ./scripts/spark-cluster/submit-job.sh scripts/ingest/test_chicago_ingestion.py --provider chicago
    ./scripts/spark-cluster/submit-job.sh scripts/ingest/test_chicago_ingestion.py --max-records 100000
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add repo to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--storage-path', type=str, default='/shared/storage',
                        help='Storage path (default: /shared/storage)')
    parser.add_argument('--provider', type=str, default='all',
                        choices=['all', 'chicago', 'cook_county'],
                        help='Provider to test (default: all)')
    parser.add_argument('--max-records', type=int, default=100000,
                        help='Max records per endpoint (default: 100000)')
    parser.add_argument('--write-batch-size', type=int, default=50000,
                        help='Records per Delta write batch (default: 50000)')
    args = parser.parse_args()

    import json
    from datapipelines.base.ingestor_engine import IngestorEngine
    from datapipelines.providers.chicago.chicago_provider import create_chicago_provider
    from datapipelines.providers.cook_county.cook_county_provider import create_cook_county_provider
    from orchestration.common.spark_session import get_spark

    repo_root = Path(__file__).resolve().parents[2]

    # Load storage config
    with open(repo_root / 'configs/storage.json') as f:
        storage_cfg = json.load(f)

    # Override roots with storage path
    storage_cfg['roots'] = {
        k: v.replace('storage/', f'{args.storage_path}/')
        for k, v in storage_cfg['roots'].items()
    }

    logger.info(f'Storage path: {args.storage_path}')
    logger.info(f'Max records per endpoint: {args.max_records}')
    logger.info(f'Write batch size: {args.write_batch_size}')

    # Initialize Spark
    spark = get_spark(app_name='test_chicago_ingestion')

    # Provider factories
    provider_factories = {
        'chicago': create_chicago_provider,
        'cook_county': create_cook_county_provider,
    }

    providers_to_run = list(provider_factories.keys()) if args.provider == 'all' else [args.provider]

    for provider_name in providers_to_run:
        logger.info(f'=' * 60)
        logger.info(f'Processing provider: {provider_name}')
        logger.info(f'=' * 60)

        try:
            factory = provider_factories[provider_name]
            provider = factory(
                spark=spark,
                docs_path=repo_root,
                storage_path=args.storage_path
            )
            logger.info(f'Created provider: {provider.provider_id}')
            logger.info(f'Available endpoints: {provider.list_work_items()}')

            # Create engine
            engine = IngestorEngine(provider, storage_cfg)

            # Run ingestion
            results = engine.run(
                work_items=None,  # All endpoints
                write_batch_size=args.write_batch_size,
                max_records=args.max_records,
                silent=False
            )

            logger.info(
                f'{provider_name}: {results.completed_work_items}/{results.total_work_items} '
                f'work items, {results.total_records:,} total records'
            )

        except Exception as e:
            logger.error(f'Error processing {provider_name}: {e}', exc_info=True)
            raise

    spark.stop()
    logger.info('Chicago/Cook County ingestion complete')


if __name__ == '__main__':
    main()
