# 3D Mesh Generation Inference Server

This is an inference server for generating 3D meshes from text prompts using machine learning models.

## Overview

The project consists of the following key components:

- `app/` - Contains the FastAPI application for the HTTP API endpoints. Handles incoming requests and returning responses.

- `inference/` - Contains the inference server code. Loads the ML model and runs the inference loop to process tasks.

- `database/` - Contains the database interface using SQLAlchemy to manage persistent storage of tasks. 

- `state.py` - Contains global state objects used for synchronization between the FastAPI app and inference server.

## Key Files

- `app/main.py` - FastAPI application initialization and includes the API router.

- `app/tasks.py` - API endpoints for submitting a task and getting task status/results. 

- `app/models.py` - Pydantic models for the API request/response schema.

- `app/utils.py` - Utility functions for the API app.

- `inference/inference_server.py` - Main inference server runner. Loads model and processes tasks in a loop.

- `database/db_manager.py` - Functions to interface with the database for tasks.

- `state.py` - Global state objects used for syncing between app and inference server.

## Usage

To start the server:

1. Install dependencies
2. Run `uvicorn main:app` 

The main FastAPI app will launch. 
The inference server will automatically start up in a background thread.

To submit a task:

- POST to `/generate` endpoint with a `GenerationTaskRequest` body

To check status and get results:

- GET `/task/{task_id}/status` to check if processing is complete
- GET `/tasks/{task_id}/results` to download the generated .obj file

The results will be saved to the current working directory.

