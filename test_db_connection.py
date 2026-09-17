from educacao.config.database import PostgresConfig, get_connection


def main() -> None:
    config = PostgresConfig()
    print(f"PostgreSQL alvo: {config.user}@{config.host}:{config.port}/{config.dbname}")

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version();")
                version = cur.fetchone()[0]
                cur.execute("SELECT current_database(), current_user;")
                database, user = cur.fetchone()
        print("Conexão bem-sucedida:")
        print(f"  database: {database}")
        print(f"  user: {user}")
        print(f"  version: {version}")
    except Exception as exc:
        print("Falha ao conectar no PostgreSQL:")
        print(exc)
        raise


if __name__ == "__main__":
    main()
