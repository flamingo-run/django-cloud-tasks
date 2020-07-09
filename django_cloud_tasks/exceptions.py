class GoogleCredentialsException(Exception):
    def __init__(self):
        message = 'GCP_JSON or GCP_B64 env variable not set properly'
        super().__init__(message)
