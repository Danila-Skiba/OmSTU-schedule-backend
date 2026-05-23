import grpc
from concurrent import futures
from app import auth_pb2
from app import auth_pb2_grpc
from app.services.auth import decode_token
from app.database import SessionLocal
from app.models.user import User


class AuthServicer(auth_pb2_grpc.AuthServiceServicer):
    def ValidateToken(self, request, context):
        token = request.token
        db = SessionLocal()
        
        try:
            payload = decode_token(token)
            if not payload:
                return auth_pb2.TokenResponse(valid=False)

            user = db.query(User).filter(User.id == payload["sub"]).first()
            if not user:
                return auth_pb2.TokenResponse(valid=False)

            return auth_pb2.TokenResponse(
                valid=True,
                user_id=str(user.id),
                email=user.email,
            )
        finally:
            db.close()


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    auth_pb2_grpc.add_AuthServiceServicer_to_server(AuthServicer(), server)
    server.add_insecure_port("[::]:50051")
    server.start()
    server.wait_for_termination()