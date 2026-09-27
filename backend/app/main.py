from fastapi import FastAPI

app = FastAPI(
    title="Vision Detector Api",
    version="0.1.0"
)

@app.get("/")
def root():
    return{
        "nessage":"Vision detector is running"
    }
    
    
    
    
    
@app.get("/health")
def health():
    return{
        "status":"ok"
    }



