import os
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List

class ConversionRequest:
    def __init__(self, filename: str, original_path: str):
        self.id = str(uuid.uuid4())
        self.filename = filename
        self.original_path = original_path
        self.text_result: Optional[str] = None
        self.created_at = datetime.now()
        self.processed_at: Optional[datetime] = None
        self.status = "pending"  # pending, processing, completed, failed
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "filename": self.filename,
            "text_result": self.text_result,
            "created_at": self.created_at.isoformat(),
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "status": self.status
        }

class ConversionManager:
    def __init__(self):
        self.requests = {}
        
    def create_request(self, filename: str, filepath: str) -> ConversionRequest:
        request = ConversionRequest(filename, filepath)
        self.requests[filename] = request
        return request
        
    def get_request(self, filename: str) -> Optional[ConversionRequest]:
        return self.requests.get(filename)
        
    def update_request(self, filename: str, text_result: str, status: str) -> bool:
        request = self.get_request(filename)
        if request:
            request.text_result = text_result
            request.status = status
            request.processed_at = datetime.now()
            return True
        return False
        
    def cleanup_old_requests(self, max_age_hours: int = 24):
        current_time = datetime.now()
        to_remove = []
        
        for filename, request in self.requests.items():
            age = current_time - request.created_at
            if age.total_seconds() > max_age_hours * 3600:
                to_remove.append(filename)
                
        for filename in to_remove:
            del self.requests[filename]
            
    def get_all_requests(self) -> List[ConversionRequest]:
        return list(self.requests.values())