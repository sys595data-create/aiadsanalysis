import boto3
import json
from botocore.client import Config
from backend.config import settings


def _client():
    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def upload_json(key: str, data: dict | list) -> str:
    body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    _client().put_object(
        Bucket=settings.r2_bucket_name,
        Key=key,
        Body=body,
        ContentType="application/json",
    )
    return key


def upload_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    _client().put_object(
        Bucket=settings.r2_bucket_name,
        Key=key,
        Body=data,
        ContentType=content_type,
    )
    return key


def upload_file(key: str, local_path: str, content_type: str = "application/octet-stream") -> str:
    with open(local_path, "rb") as f:
        _client().put_object(
            Bucket=settings.r2_bucket_name,
            Key=key,
            Body=f,
            ContentType=content_type,
        )
    return key


def download_json(key: str) -> dict | list:
    resp = _client().get_object(Bucket=settings.r2_bucket_name, Key=key)
    return json.loads(resp["Body"].read().decode("utf-8"))


def list_keys(prefix: str) -> list[str]:
    paginator = _client().get_paginator("list_objects_v2")
    keys = []
    for page in paginator.paginate(Bucket=settings.r2_bucket_name, Prefix=prefix):
        for obj in page.get("Contents", []):
            keys.append(obj["Key"])
    return keys


def presigned_url(key: str, expires_in: int = 86400) -> str:
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.r2_bucket_name, "Key": key},
        ExpiresIn=expires_in,
    )


def delete_prefix(prefix: str):
    keys = list_keys(prefix)
    if not keys:
        return
    _client().delete_objects(
        Bucket=settings.r2_bucket_name,
        Delete={"Objects": [{"Key": k} for k in keys]},
    )
