from fastapi import FastAPI

app=FastAPI(title='Velo Backend')

@app.get('/')
def root():
    return {'status':'ok'}
