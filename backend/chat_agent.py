import os
import json
from typing import AsyncGenerator, Dict, List, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

class ChatAgent:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0.2,
            google_api_key=os.getenv("GEMINI_API_KEY"),
            streaming=True,  # Enable streaming
        )
        self.system_prompt = """You are an expert in US healthcare X12 EDI files (837, 835, 834).
        Answer questions based ONLY on the file content provided in the context.
        If the information is not in the file, say "I don't see that information in this file."
        Be concise and helpful. Explain EDI terms in plain English."""

    async def stream_response(self, query: str, parsed_data: List[Dict], file_type: str) -> AsyncGenerator[str, None]:
        """Stream the AI response token by token."""
        # Build context
        segment_summary = []
        for seg in parsed_data[:20]:  # Limit to first 20 segments
            seg_id = seg.get("id", "")
            elements = seg.get("elements", [])
            segment_summary.append(f"{seg_id}: {elements}")
        
        context = f"""
        File Type: {file_type}
        
        File Content (first 20 segments):
        {chr(10).join(segment_summary)}
        
        Question: {query}
        """
        
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=context)
        ]
        
        # Stream tokens
        async for chunk in self.llm.astream(messages):
            if chunk.content:
                yield chunk.content

# Singleton
_agent = None

def get_agent():
    global _agent
    if _agent is None:
        _agent = ChatAgent()
    return _agent