"""Initialize the onepage database in the existing PostgreSQL container."""
import subprocess
import sys


def main():
    cmd = [
        "docker", "exec", "training-postgres",
        "psql", "-U", "training",
        "-c", "CREATE DATABASE onepage;"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        if "already exists" in result.stderr:
            print("Database 'onepage' already exists, skipping.")
        else:
            print(f"Error: {result.stderr}")
            sys.exit(1)
    else:
        print("Database 'onepage' created successfully.")


if __name__ == "__main__":
    main()
