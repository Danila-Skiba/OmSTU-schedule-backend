import grpc
from app import auth_pb2
from app import auth_pb2_grpc
from app.config import AUTH_GRPC_URL


def validate_token_grpc(token: str) -> dict:
    try:
        with grpc.insecure_channel(AUTH_GRPC_URL) as channel:
            stub = auth_pb2_grpc.AuthServiceStub(channel)
            response = stub.ValidateToken(
                auth_pb2.TokenRequest(token=token),
                timeout=5,
            )
            return {
                "valid": response.valid,
                "user_id": response.user_id,
                "email": response.email,
            }
    except Exception as e:
        print(f"gRPC ошибка: {e}")
        return {"valid": False}