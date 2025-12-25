"""
Data models for job offers.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional
import json


@dataclass
class JobOffer:
    """Represents a scraped job offer."""
    
    url: str
    title: str
    company: str
    source: str  # justjoin, theprotocol, pracuj, linkedin
    
    # Optional metadata fields
    location: Optional[str] = None
    salary: Optional[str] = None
    experience_level: Optional[str] = None
    employment_type: Optional[str] = None
    work_mode: Optional[str] = None  # remote/hybrid/onsite
    
    # Full job description (all content combined)
    description: str = ""
    
    # Metadata
    scraped_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data["scraped_at"] = self.scraped_at.isoformat()
        return data
    
    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
    
    def to_text(self) -> str:
        """Convert to human-readable text format."""
        lines = [
            f"{'='*60}",
            f"JOB OFFER: {self.title}",
            f"{'='*60}",
            f"",
            f"Company: {self.company}",
            f"Source: {self.source}",
            f"URL: {self.url}",
            f"",
        ]
        
        if self.location:
            lines.append(f"📍 Location: {self.location}")
        if self.salary:
            lines.append(f"💰 Salary: {self.salary}")
        if self.experience_level:
            lines.append(f"📊 Experience: {self.experience_level}")
        if self.employment_type:
            lines.append(f"📋 Employment: {self.employment_type}")
        if self.work_mode:
            lines.append(f"🏠 Work Mode: {self.work_mode}")
        
        lines.append("")
        
        if self.description:
            lines.append("📝 Description:")
            lines.append("-" * 40)
            lines.append(self.description)
            lines.append("-" * 40)
        
        lines.append("")
        lines.append(f"Scraped at: {self.scraped_at.strftime('%Y-%m-%d %H:%M:%S')}")
        
        return "\n".join(lines)
    
    def to_markdown(self) -> str:
        """Convert to Markdown format."""
        lines = [
            f"# {self.title}",
            f"",
            f"**Company:** {self.company}  ",
            f"**Source:** {self.source}  ",
            f"**URL:** [{self.url}]({self.url})",
            f"",
            "## Details",
            "",
        ]
        
        if self.location:
            lines.append(f"- **Location:** {self.location}")
        if self.salary:
            lines.append(f"- **Salary:** {self.salary}")
        if self.experience_level:
            lines.append(f"- **Experience Level:** {self.experience_level}")
        if self.employment_type:
            lines.append(f"- **Employment Type:** {self.employment_type}")
        if self.work_mode:
            lines.append(f"- **Work Mode:** {self.work_mode}")
        
        lines.append("")
        
        if self.description:
            lines.append("## Description")
            lines.append("")
            lines.append(self.description)
            lines.append("")
        
        lines.append("---")
        lines.append(f"*Scraped at: {self.scraped_at.strftime('%Y-%m-%d %H:%M:%S')}*")
        
        return "\n".join(lines)
