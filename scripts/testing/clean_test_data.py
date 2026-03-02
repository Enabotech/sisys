#!/usr/bin/env python3
"""
Test Data Cleanup Script
Usage: python scripts/testing/clean_test_data.py [options]

Options:
  --all           Clean all test data (databases, caches, files)
  --databases     Clean only test databases
  --cache         Clean only test caches (Redis, Qdrant)
  --files         Clean only test files (MinIO objects)
  --dry-run       Show what would be cleaned without actually cleaning
  --help          Show this help message

Examples:
  python scripts/testing/clean_test_data.py --all
  python scripts/testing/clean_test_data.py --databases --dry-run
"""

import argparse
import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from minio import Minio
    from neo4j import GraphDatabase
    from psycopg2 import connect, sql
    from qdrant_client import QdrantClient
    from redis import Redis
except ImportError as e:
    print(f"❌ Missing dependency: {e}")
    print("Please install test dependencies: poetry install --with test")
    sys.exit(1)


class TestDataCleaner:
    """Clean test data from various storage systems."""

    def __init__(
        self,
        postgres_url: str | None = None,
        redis_url: str | None = None,
        qdrant_url: str | None = None,
        minio_endpoint: str | None = None,
        minio_access_key: str | None = None,
        minio_secret_key: str | None = None,
        neo4j_uri: str | None = None,
        neo4j_user: str | None = None,
        neo4j_password: str | None = None,
        dry_run: bool = False,
    ):
        self.postgres_url = postgres_url or os.getenv(
            "TEST_POSTGRES_URL", "postgresql://test_user:test_password@localhost:5432/test_db"
        )
        self.redis_url = redis_url or os.getenv("TEST_REDIS_URL", "redis://localhost:6379/0")
        self.qdrant_url = qdrant_url or os.getenv("TEST_QDRANT_URL", "http://localhost:6333")
        self.minio_endpoint = minio_endpoint or os.getenv("TEST_MINIO_ENDPOINT", "localhost:9000")
        self.minio_access_key = minio_access_key or os.getenv("TEST_MINIO_ACCESS_KEY", "test_minio")
        self.minio_secret_key = minio_secret_key or os.getenv(
            "TEST_MINIO_SECRET_KEY", "test_minio_password"
        )
        self.neo4j_uri = neo4j_uri or os.getenv("TEST_NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_user = neo4j_user or os.getenv("TEST_NEO4J_USER", "neo4j")
        self.neo4j_password = neo4j_password or os.getenv(
            "TEST_NEO4J_PASSWORD", "test_neo4j_password"
        )
        self.dry_run = dry_run

    def clean_postgres(self):
        """Clean PostgreSQL test database."""
        print("\n🗄️  Cleaning PostgreSQL test database...")
        try:
            conn = connect(self.postgres_url)
            cursor = conn.cursor()

            # Get all tables
            cursor.execute(
                """
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY tablename;
            """
            )
            tables = cursor.fetchall()

            if not tables:
                print("  No tables found")
                return

            # Drop all tables
            for (table_name,) in tables:
                if self.dry_run:
                    print(f"  Would drop table: {table_name}")
                else:
                    print(f"  Dropping table: {table_name}")
                    cursor.execute(
                        sql.SQL("DROP TABLE IF EXISTS {} CASCADE").format(
                            sql.Identifier(table_name)
                        )
                    )

            if not self.dry_run:
                conn.commit()
                print("  ✅ PostgreSQL cleaned")

            cursor.close()
            conn.close()

        except Exception as e:
            print(f"  ❌ Error cleaning PostgreSQL: {e}")

    def clean_redis(self):
        """Clean Redis test database."""
        print("\n🔴 Cleaning Redis test database...")
        try:
            redis_client = Redis.from_url(self.redis_url)
            keys = redis_client.keys("*")

            if not keys:
                print("  No keys found")
                return

            if self.dry_run:
                print(f"  Would delete {len(keys)} keys")
            else:
                print(f"  Deleting {len(keys)} keys")
                redis_client.delete(*keys)
                print("  ✅ Redis cleaned")

            redis_client.close()

        except Exception as e:
            print(f"  ❌ Error cleaning Redis: {e}")

    def clean_qdrant(self):
        """Clean Qdrant test collections."""
        print("\n🎯 Cleaning Qdrant test collections...")
        try:
            client = QdrantClient(url=self.qdrant_url)
            collections = client.get_collections().collections

            if not collections:
                print("  No collections found")
                return

            for collection in collections:
                if self.dry_run:
                    print(f"  Would delete collection: {collection.name}")
                else:
                    print(f"  Deleting collection: {collection.name}")
                    client.delete_collection(collection.name)

            if not self.dry_run:
                print("  ✅ Qdrant cleaned")

            client.close()

        except Exception as e:
            print(f"  ❌ Error cleaning Qdrant: {e}")

    def clean_minio(self):
        """Clean MinIO test buckets."""
        print("\n🪣 Cleaning MinIO test buckets...")
        try:
            client = Minio(
                self.minio_endpoint,
                access_key=self.minio_access_key,
                secret_key=self.minio_secret_key,
                secure=False,
            )

            buckets = client.list_buckets()

            for bucket in buckets:
                if self.dry_run:
                    print(f"  Would delete bucket: {bucket.name}")
                else:
                    print(f"  Deleting bucket: {bucket.name}")
                    # Delete all objects in bucket first
                    objects = client.list_objects(bucket.name, recursive=True)
                    for obj in objects:
                        client.remove_object(bucket.name, obj.object_name)
                    # Delete bucket
                    client.remove_bucket(bucket.name)

            if not self.dry_run:
                print("  ✅ MinIO cleaned")

        except Exception as e:
            print(f"  ❌ Error cleaning MinIO: {e}")

    def clean_neo4j(self):
        """Clean Neo4j test database."""
        print("\n🕸️  Cleaning Neo4j test database...")
        try:
            driver = GraphDatabase.driver(
                self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password)
            )

            with driver.session() as session:
                if self.dry_run:
                    print("  Would delete all nodes and relationships")
                else:
                    print("  Deleting all nodes and relationships")
                    session.run("MATCH (n) DETACH DELETE n")
                    print("  ✅ Neo4j cleaned")

            driver.close()

        except Exception as e:
            print(f"  ❌ Error cleaning Neo4j: {e}")

    def clean_all(self):
        """Clean all test data."""
        print("🧹 Starting full test data cleanup...")
        if self.dry_run:
            print("⚠️  DRY RUN - No actual changes will be made\n")
        else:
            print("⚠️  This will delete ALL test data!\n")

        self.clean_postgres()
        self.clean_redis()
        self.clean_qdrant()
        self.clean_minio()
        self.clean_neo4j()

        print("\n✅ Test data cleanup complete!")


def main():
    parser = argparse.ArgumentParser(description="Clean test data from various storage systems")
    parser.add_argument("--all", action="store_true", help="Clean all test data")
    parser.add_argument("--databases", action="store_true", help="Clean only test databases")
    parser.add_argument("--cache", action="store_true", help="Clean only test caches")
    parser.add_argument("--files", action="store_true", help="Clean only test files")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be cleaned")

    args = parser.parse_args()

    if not any([args.all, args.databases, args.cache, args.files]):
        print("❌ Please specify what to clean (--all, --databases, --cache, or --files)")
        parser.print_help()
        sys.exit(1)

    cleaner = TestDataCleaner(dry_run=args.dry_run)

    if args.all:
        cleaner.clean_all()
    else:
        if args.databases:
            cleaner.clean_postgres()
            cleaner.clean_neo4j()
        if args.cache:
            cleaner.clean_redis()
            cleaner.clean_qdrant()
        if args.files:
            cleaner.clean_minio()


if __name__ == "__main__":
    main()
