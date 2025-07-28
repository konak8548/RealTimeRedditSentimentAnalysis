Real-Time Reddit Sentiment Analysis Pipeline - Project Documentation
1. Introduction
This project implements a real-time data pipeline to analyze sentiments of Reddit posts mentioning the keyword 'Donald Trump'. The pipeline uses a Dockerized Python application that streams Reddit posts, performs emotion detection using the pre-trained model 'j-hartmann/emotion-english-distilroberta-base', and sends the results to Azure Event Hub. The data is processed via Azure Stream Analytics and stored in an Azure SQL Database. Finally, Power BI Desktop visualizes the emotions in real-time using a Tree Map.
2. Pipeline Workflow
1.  Reddit Ingestion : A Python application uses PRAW to stream Reddit posts.
2.  Sentiment Analysis : Uses HuggingFace model 'j-hartmann/emotion-english-distilroberta-base'.
3.  Event Hub : Processed events are pushed to Azure Event Hub.
4.  Stream Analytics Job : Reads from Event Hub, aggregates emotions, and outputs to Azure SQL DB.
5.  Power BI Desktop : Connects to SQL DB (DirectQuery) to visualize real-time emotion counts.
3. Docker Image Creation & Deployment
    3.1. Requirements
- Docker installed
- Azure CLI installed
- Azure Container Registry (ACR)
- Azure Container Instance (ACI)
    3.2. Build Docker Image
```bash
docker build -t reddit-stream:latest .
```

    3.3. Tag and Push Image to ACR
```bash
docker tag reddit-stream:latest redditingestacr.azurecr.io/reddit-stream:latest
az acr login --name redditingestacr
docker push redditingestacr.azurecr.io/reddit-stream:latest
```

    3.4. Deploy Docker Image to ACI
```bash
az container create --resource-group proj_rg --name reddit-streamer --image redditingestacr.azurecr.io/reddit-stream:latest --cpu 2 --memory 4 --registry-login-server redditingestacr.azurecr.io --registry-username redditingestacr --registry-password <ACR_PASSWORD> --environment-variables REDDIT_CLIENT_ID=<client_id> REDDIT_CLIENT_SECRET=<client_secret> REDDIT_USER_AGENT='SentimentStreamBot/1.0' EVENTHUB_CONNECTION_STRING='<eventhub_connection>' EVENTHUB_NAME='twitterdata'
```

Note:
Even though we’re processing Reddit posts, the Event Hub name chosen is twitterdata. This name is just an identifier and does not mean the data is coming from Twitter.
4. Python Ingestion Script
The `ingest.py` script streams Reddit posts, filters them based on keywords, performs sentiment analysis, and publishes results to Event Hub in JSON format.
5. Azure Stream Analytics Job
The following query is used in Stream Analytics to aggregate emotion counts:
```sql
SELECT
    emotion,
    COUNT(*) AS count,
    System.Timestamp AS windowEnd
INTO
    [SQL_DB_Output]
FROM
    [twitterdata] TIMESTAMP BY created_utc
GROUP BY
    emotion, HOPPINGWINDOW(second, 1800, 10)
```

6. Power BI Desktop Integration
1. Connect Power BI Desktop to the Azure SQL Database using  DirectQuery .
2. Build a Tree Map visual using 'emotion' as category and 'count' as value.
3. Enable  Auto Page Refresh  in report settings and set interval to 30-60 seconds.
7. Key CLI Commands
```bash
az login
az acr login --name redditingestacr
az container logs --resource-group proj_rg --name reddit-streamer
az sql db query --name <SQL_DB_Name> --query "SELECT TOP 10 * FROM EmotionCounts ORDER BY windowEnd DESC;"
```

