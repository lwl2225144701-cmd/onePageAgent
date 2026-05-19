"""Initialize MinIO buckets for OnePage."""
import subprocess
import sys


def main():
    cmd = [
        "docker", "run", "--rm", "--network", "infra_default",
        "minio/mc:latest",
        "/bin/sh", "-c",
        (
            "mc alias set local http://training-minio:9000 minioadmin minioadmin && "
            "mc mb --ignore-existing local/onepage-uploads && "
            "mc mb --ignore-existing local/onepage-materials"
        ),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        sys.exit(1)
    print("MinIO buckets created successfully: onepage-uploads, onepage-materials")


if __name__ == "__main__":
    main()
