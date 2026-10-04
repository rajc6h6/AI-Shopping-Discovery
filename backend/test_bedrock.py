import asyncio
from app.config import Settings
from app.parser import parse_chat

async def main():
    settings = Settings()
    print(f"Region: {settings.aws_region}")
    print(f"Model: {settings.bedrock_model_parse}")
    print(f"Token length: {len(settings.aws_bearer_token_bedrock)}")
    
    text = "AI: I recommend getting a pair of classic white Converse sneakers. They go with everything."
    print(f"\nSending chat: '{text}'")
    
    try:
        result = await parse_chat(
            text=text,
            model=settings.bedrock_model_parse,
            aws_bearer_token_bedrock=settings.aws_bearer_token_bedrock,
            aws_region=settings.aws_region,
        )
        print("\nSUCCESS! Parsed items:")
        for item in result.items:
            print(f"- {item.brand} {item.model_name} {item.category} ({item.colour})")
    except Exception as e:
        print("\nERROR:")
        print(str(e))

if __name__ == "__main__":
    asyncio.run(main())
