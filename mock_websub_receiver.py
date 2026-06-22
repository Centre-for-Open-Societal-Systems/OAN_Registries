from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
import json, uvicorn, boto3, os
from datetime import datetime
import uuid

# 🔧 S3 CONFIG (Manager's exact paths)
S3_BUCKET = "a2c-webhook"
S3_RESPONE = "respone"
S3_OTP = "otp"
AWS_REGION = "ap-south-1"

# Initialize S3 client
s3_client = boto3.client('s3', region_name=AWS_REGION)


def push_to_s3(data, folder):
    """Upload JSON to S3 under specified folder"""
    try:
        # Unique filename: 2026-05-29T12-30-45_abc12345.json
        ts = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        uid = uuid.uuid4().hex[:8]
        key = f"{folder}/{ts}_{uid}.json"

        # Upload
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=json.dumps(data, indent=2, default=str),
            ContentType='application/json'
        )
        print(f"✅ PUSHED TO S3: s3://{S3_BUCKET}/{key}")
        return True
    except Exception as e:
        print(f"❌ S3 Upload Failed: {e}")
        return False


app = FastAPI()


@app.post('/')
async def receive_data(request: Request):
    body = await request.body()
    content_type = request.headers.get('content-type', '')

    # Handle form-encoded (auth/registration)
    if 'application/x-www-form-urlencoded' in content_type:
        text = body.decode('utf-8', errors='replace')
        if 'grant_type=client_credentials' in text:
            print('🔑 Auth request')
            return JSONResponse(content={"access_token": "mock-token-123", "token_type": "bearer", "expires_in": 3600})
        return PlainTextResponse(content='hub.mode=accepted', status_code=200)

    # Handle JSON (webhook or OTP)
    if 'application/json' in content_type:
        try:
            data = json.loads(body)
            print('\n======= RECEIVED =======')
            print(json.dumps(data, indent=2))
            print('==========================\n')

            # Decide: OTP or Webhook?
            data_text = json.dumps(data).lower()
            is_otp = 'otp' in data_text or 'transactionid' in data_text

            folder = S3_OTP if is_otp else S3_RESPONE
            print(f"📦 Pushing to: s3://{S3_BUCKET}/{folder}/")
            push_to_s3(data, folder)

        except Exception as e:
            print(f"⚠️ Error: {e}")

    return PlainTextResponse(content='hub.mode=accepted', status_code=200)


if __name__ == '__main__':
    print(f"🚀 Running on http://0.0.0.0:9002")
    print(f"📦 S3: s3://{S3_BUCKET}/")
    print(f"   → Webhooks: {S3_RESPONE}/")
    print(f"   → OTPs:     {S3_OTP}/")
    uvicorn.run(app, host='0.0.0.0', port=9002)