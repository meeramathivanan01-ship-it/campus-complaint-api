from fastapi import FastAPI

app = FastAPI(
    title="Campus Complaint & Maintenance Management API",
    description="API for managing campus complaints, maintenance requests, assignments, and follow-up feedback.",
    version="0.1.0",
)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Campus Complaint & Maintenance Management API is running."}
