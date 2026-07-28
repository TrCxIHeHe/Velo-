from functools import lru_cache
from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/scooter_db"

    # Access tokens are signed RS256 (asymmetric) per the security
    # architecture doc. These are a dev-only keypair, safe to publish —
    # generate a real one (`openssl genrsa`/`cryptography`) and set both
    # via env before deploying anywhere real users can reach.
    JWT_ALGORITHM: str = "RS256"
    JWT_PRIVATE_KEY: str = """-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC50e0ZaNMB4j7R
ZbxaZtcI1GbCPJRX2CL3oIfXCLGC50gOhgECb+VJYsJt6+4mD3xRRcd/wkzOkNVq
2ves32VjVaJxzP4wrdAw8TB6xa+7iMVZTj0hLagRr0S14lTGKxIp28HhgI0Cg8/D
rOJ8iQLuFC4EWFRAxDo5499UTD5gjw+viAwouuCzkOCsy4HStjN4F5AciohWlh2e
eL0pKsgMXczYq22xR8YId5yIO7J8lwI+KonhPihEEE3Edcnthgfwk1qlE+Dtf2HI
R+X5IjtwXU+XwqnwgJO9nX5IJZLcTNd6l+bDeXCAskiqepYR2wnZO6e/loCtuEFD
4G/5jjXfAgMBAAECggEAG05Ib6/yNfgnsACptYUgO0lvEkLxr5jwxn++BnDeGPTg
p1W0x0VnJaoQFTQSymADLjQ5VUJZpA8vdWTY+XvYe8jlNqDfh4q7Kb3/mEL9iGrY
ST/QhtQdOwAM8kdgmsBQinsjGf6YehKhkMkSfSdrGU441uWd9+h9/+zG8C3GCs0q
t2xu7Ci6RTiJA42eWOnzF0cqjuhooHvEMLCUbBrwyGeBbqGKFFYgmm5xdDrsM161
0R1lkmpmWnL4kHvBJRo6H0VKDfAJ2xFf7x8ZLZSaA2hLBtHa5vu7MRwW0pheje3s
pyqYnulZJsLilUKnhv9dHXJK1hpeNMCq+cC3h/ic3QKBgQDtFCViCRP9OpkgNmjO
/FoqG0+qR0E/j/YRjKVV1gAvDgKEHchOCF5J1AmRHIzgp9bP/S4dCmWchVPwTSx7
kn2ykyNlMB/xmIvjLsJAPEbcgHI6sq8RZHh0bj/BrwymlYgLIGTq/THCPbrkzIfW
RsbJpMwWdTo4E9Lbf+IC5Pj+awKBgQDIpn4nlteyBIeRka6UhPvE2qCj5N1EO7Iy
vBB8jyO3P44ZsG2IGsjloNgcVepTZfVeel8RGIEz70r6csx8YvG0vfWvbuqOjnSk
556nP4cTfyKWR99bHqtAsC800xFsPDq9yGppvrR0FWB8rXghjwGWS97YsW119eMe
YZTVgO2bXQKBgFLqjdyIwkX5nZ6HiQaDeeFqJeWvACID7pLatuSbcPsEEls0s16f
TKLTlvj6nEbiTJ33tY4QmdMxSlcsFpetd2riTSnRuApeSOaO7v9aVYo/HjRrVBFo
KzzFZmUOHQWSHL+Pd9w765A82MW2xvdpT5MsoPhlzZPZUxDT3C8Y+AC7AoGBAKk+
fiSIgHFgjrVDi10s+mxl+J+lmNlH/Rv8M2/NENQtoH+cqBboeNHvpLnp4hfsZVYG
pA94eurCiZzMnhzBHJ1WqVgLl38dO9goolLyK85PK25VO1nReaO7uGW3Lvf7qZSQ
6uk8+Vr8+QDRFQZBaJZMcrCWn/yiparnpjGcaU7lAoGAdCACXwn0USRwnq9D7bRu
eldciAEABt8XobKG7sSf909aPwoGez2Rd9oQ9KUJoFBrmVMGHVvnVG9gp+SVsIDm
pRcbbqK3Mf94mlHDzes+/aNT+C+5Ev4XICGxbJnCMj+eimbcmQ8c6igyjLi0DVf4
i2i+NC21+PKymFTvnYfUIyE=
-----END PRIVATE KEY-----"""
    JWT_PUBLIC_KEY: str = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAudHtGWjTAeI+0WW8WmbX
CNRmwjyUV9gi96CH1wixgudIDoYBAm/lSWLCbevuJg98UUXHf8JMzpDVatr3rN9l
Y1Wiccz+MK3QMPEwesWvu4jFWU49IS2oEa9EteJUxisSKdvB4YCNAoPPw6zifIkC
7hQuBFhUQMQ6OePfVEw+YI8Pr4gMKLrgs5DgrMuB0rYzeBeQHIqIVpYdnni9KSrI
DF3M2KttsUfGCHeciDuyfJcCPiqJ4T4oRBBNxHXJ7YYH8JNapRPg7X9hyEfl+SI7
cF1Pl8Kp8ICTvZ1+SCWS3EzXepfmw3lwgLJIqnqWEdsJ2Tunv5aArbhBQ+Bv+Y41
3wIDAQAB
-----END PUBLIC KEY-----"""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    FIREBASE_PROJECT_ID: str = "your-project-id"
    FIREBASE_SERVICE_ACCOUNT_PATH: str = "./firebase-service-account.json"

    ENVIRONMENT: str = "development"
    API_V1_PREFIX: str = "/api/v1"

    WALLET_DEFAULT_CURRENCY: str = "INR"
    WALLET_MIN_RIDE_BALANCE: int = 20

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Ride Token (QR)
    RIDE_TOKEN_SECRET: str = "dev_ride_secret_change_before_deploy"
    RIDE_TOKEN_ALGORITHM: str = "HS256"
    RIDE_TOKEN_TTL_SECONDS: int = 30
    VEHICLE_BATTERY_MIN_THRESHOLD: int = 20

    # CORS — comma-separated origin list. "*" only ever makes sense in dev;
    # main.py refuses to combine it with allow_credentials=True.
    CORS_ORIGINS: str = "*"

    # Razorpay
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""

    # Firebase Cloud Messaging
    FCM_ENABLED: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
