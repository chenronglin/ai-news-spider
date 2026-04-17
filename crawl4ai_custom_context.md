# Crawl4AI Custom LLM Context
Generated on: 2026-04-16T09:29:35.225Z
Total files: 8
Estimated tokens: 34,915

---

## Simple Crawling - Full Content
Component ID: simple_crawling
Context Type: memory
Estimated tokens: 2,390

## Simple Crawling

Basic web crawling operations with AsyncWebCrawler, configurations, and response handling.

### Basic Setup

```python
import asyncio
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

async def main():
    browser_config = BrowserConfig()  # Default browser settings
    run_config = CrawlerRunConfig()   # Default crawl settings

    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(
            url="https://example.com",
            config=run_config
        )
        print(result.markdown)

if __name__ == "__main__":
    asyncio.run(main())
```

### Understanding CrawlResult

```python
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from crawl4ai.content_filter_strategy import PruningContentFilter

config = CrawlerRunConfig(
    markdown_generator=DefaultMarkdownGenerator(
        content_filter=PruningContentFilter(threshold=0.6),
        options={"ignore_links": True}
    )
)

result = await crawler.arun("https://example.com", config=config)

# Different content formats
print(result.html)                    # Raw HTML
print(result.cleaned_html)            # Cleaned HTML  
print(result.markdown.raw_markdown)   # Raw markdown
print(result.markdown.fit_markdown)   # Filtered markdown

# Status information
print(result.success)      # True/False
print(result.status_code)  # HTTP status (200, 404, etc.)

# Extracted content
print(result.media)        # Images, videos, audio
print(result.links)        # Internal/external links
```

### Basic Configuration Options

```python
run_config = CrawlerRunConfig(
    word_count_threshold=10,        # Min words per block
    exclude_external_links=True,    # Remove external links
    remove_overlay_elements=True,   # Remove popups/modals
    process_iframes=True,           # Process iframe content
    excluded_tags=['form', 'header']  # Skip these tags
)

result = await crawler.arun("https://example.com", config=run_config)
```

### Error Handling

```python
result = await crawler.arun("https://example.com", config=run_config)

if not result.success:
    print(f"Crawl failed: {result.error_message}")
    print(f"Status code: {result.status_code}")
else:
    print(f"Success! Content length: {len(result.markdown)}")
```

### Debugging with Verbose Logging

```python
browser_config = BrowserConfig(verbose=True)

async with AsyncWebCrawler(config=browser_config) as crawler:
    result = await crawler.arun("https://example.com")
    # Detailed logging output will be displayed
```

### Complete Example

```python
import asyncio
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

async def comprehensive_crawl():
    browser_config = BrowserConfig(verbose=True)
    
    run_config = CrawlerRunConfig(
        # Content filtering
        word_count_threshold=10,
        excluded_tags=['form', 'header', 'nav'],
        exclude_external_links=True,
        
        # Content processing
        process_iframes=True,
        remove_overlay_elements=True,
        
        # Cache control
        cache_mode=CacheMode.ENABLED
    )

    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(
            url="https://example.com",
            config=run_config
        )
        
        if result.success:
            # Display content summary
            print(f"Title: {result.metadata.get('title', 'No title')}")
            print(f"Content: {result.markdown[:500]}...")
            
            # Process media
            images = result.media.get("images", [])
            print(f"Found {len(images)} images")
            for img in images[:3]:  # First 3 images
                print(f"  - {img.get('src', 'No src')}")
            
            # Process links
            internal_links = result.links.get("internal", [])
            print(f"Found {len(internal_links)} internal links")
            for link in internal_links[:3]:  # First 3 links
                print(f"  - {link.get('href', 'No href')}")
                
        else:
            print(f"❌ Crawl failed: {result.error_message}")
            print(f"Status: {result.status_code}")

if __name__ == "__main__":
    asyncio.run(comprehensive_crawl())
```

### Working with Raw HTML and Local Files

```python
# Crawl raw HTML
raw_html = "<html><body><h1>Test</h1><p>Content</p></body></html>"
result = await crawler.arun(f"raw://{raw_html}")

# Crawl local file
result = await crawler.arun("file:///path/to/local/file.html")

# Both return standard CrawlResult objects
print(result.markdown)
```

## Table Extraction

Extract structured data from HTML tables with automatic detection and scoring.

### Basic Table Extraction

```python
import asyncio
import pandas as pd
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode

async def extract_tables():
    async with AsyncWebCrawler() as crawler:
        config = CrawlerRunConfig(
            table_score_threshold=7,  # Higher = stricter detection
            cache_mode=CacheMode.BYPASS
        )
        
        result = await crawler.arun("https://example.com/tables", config=config)
        
        if result.success and result.tables:
            # New tables field (v0.6+)
            for i, table in enumerate(result.tables):
                print(f"Table {i+1}:")
                print(f"Headers: {table['headers']}")
                print(f"Rows: {len(table['rows'])}")
                print(f"Caption: {table.get('caption', 'No caption')}")
                
                # Convert to DataFrame
                df = pd.DataFrame(table['rows'], columns=table['headers'])
                print(df.head())

asyncio.run(extract_tables())
```

### Advanced Table Processing

```python
from crawl4ai import LXMLWebScrapingStrategy

async def process_financial_tables():
    config = CrawlerRunConfig(
        table_score_threshold=8,  # Strict detection for data tables
        scraping_strategy=LXMLWebScrapingStrategy(),
        keep_data_attributes=True,
        scan_full_page=True
    )
    
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun("https://coinmarketcap.com", config=config)
        
        if result.tables:
            # Get the main data table (usually first/largest)
            main_table = result.tables[0]
            
            # Create DataFrame
            df = pd.DataFrame(
                main_table['rows'],
                columns=main_table['headers']
            )
            
            # Clean and process data
            df = clean_financial_data(df)
            
            # Save for analysis
            df.to_csv("market_data.csv", index=False)
            return df

def clean_financial_data(df):
    """Clean currency symbols, percentages, and large numbers"""
    for col in df.columns:
        if 'price' in col.lower():
            # Remove currency symbols
            df[col] = df[col].str.replace(r'[^\d.]', '', regex=True)
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        elif '%' in str(df[col].iloc[0]):
            # Convert percentages
            df[col] = df[col].str.replace('%', '').astype(float) / 100
        
        elif any(suffix in str(df[col].iloc[0]) for suffix in ['B', 'M', 'K']):
            # Handle large numbers (Billions, Millions, etc.)
            df[col] = df[col].apply(convert_large_numbers)
    
    return df

def convert_large_numbers(value):
    """Convert 1.5B -> 1500000000"""
    if pd.isna(value):
        return float('nan')
    
    value = str(value)
    multiplier = 1
    if 'B' in value:
        multiplier = 1e9
    elif 'M' in value:
        multiplier = 1e6
    elif 'K' in value:
        multiplier = 1e3
    
    number = float(re.sub(r'[^\d.]', '', value))
    return number * multiplier
```

### Table Detection Configuration

```python
# Strict table detection (data-heavy pages)
strict_config = CrawlerRunConfig(
    table_score_threshold=9,  # Only high-quality tables
    word_count_threshold=5,   # Ignore sparse content
    excluded_tags=['nav', 'footer']  # Skip navigation tables
)

# Lenient detection (mixed content pages)
lenient_config = CrawlerRunConfig(
    table_score_threshold=5,  # Include layout tables
    process_iframes=True,     # Check embedded tables
    scan_full_page=True      # Scroll to load dynamic tables
)

# Financial/data site optimization
financial_config = CrawlerRunConfig(
    table_score_threshold=8,
    scraping_strategy=LXMLWebScrapingStrategy(),
    wait_for="css:table",     # Wait for tables to load
    scan_full_page=True,
    scroll_delay=0.2
)
```

### Multi-Table Processing

```python
async def extract_all_tables():
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun("https://example.com/data", config=config)
        
        tables_data = {}
        
        for i, table in enumerate(result.tables):
            # Create meaningful names based on content
            table_name = (
                table.get('caption') or 
                f"table_{i+1}_{table['headers'][0]}"
            ).replace(' ', '_').lower()
            
            df = pd.DataFrame(table['rows'], columns=table['headers'])
            
            # Store with metadata
            tables_data[table_name] = {
                'dataframe': df,
                'headers': table['headers'],
                'row_count': len(table['rows']),
                'caption': table.get('caption'),
                'summary': table.get('summary')
            }
        
        return tables_data

# Usage
tables = await extract_all_tables()
for name, data in tables.items():
    print(f"{name}: {data['row_count']} rows")
    data['dataframe'].to_csv(f"{name}.csv")
```

### Backward Compatibility

```python
# Support both new and old table formats
def get_tables(result):
    # New format (v0.6+)
    if hasattr(result, 'tables') and result.tables:
        return result.tables
    
    # Fallback to media.tables (older versions)
    return result.media.get('tables', [])

# Usage in existing code
result = await crawler.arun(url, config=config)
tables = get_tables(result)

for table in tables:
    df = pd.DataFrame(table['rows'], columns=table['headers'])
    # Process table data...
```

### Table Quality Scoring

```python
# Understanding table_score_threshold values:
# 10: Only perfect data tables (headers + data rows)
# 8-9: High-quality tables (recommended for financial/data sites)
# 6-7: Mixed content tables (news sites, wikis)
# 4-5: Layout tables included (broader detection)
# 1-3: All table-like structures (very permissive)

config = CrawlerRunConfig(
    table_score_threshold=8,  # Balanced detection
    verbose=True  # See scoring details in logs
)
```


**📖 Learn more:** [CrawlResult API Reference](https://docs.crawl4ai.com/api/crawl-result/), [Browser & Crawler Configuration](https://docs.crawl4ai.com/core/browser-crawler-config/), [Cache Modes](https://docs.crawl4ai.com/core/cache-modes/)

---


## Simple Crawling - Diagrams & Workflows
Component ID: simple_crawling
Context Type: reasoning
Estimated tokens: 3,133

## Simple Crawling Workflows and Data Flow

Visual representations of basic web crawling operations, configuration patterns, and result processing workflows.

### Basic Crawling Sequence

```mermaid
sequenceDiagram
    participant User
    participant Crawler as AsyncWebCrawler
    participant Browser as Browser Instance
    participant Page as Web Page
    participant Processor as Content Processor
    
    User->>Crawler: Create with BrowserConfig
    Crawler->>Browser: Launch browser instance
    Browser-->>Crawler: Browser ready
    
    User->>Crawler: arun(url, CrawlerRunConfig)
    Crawler->>Browser: Create new page/context
    Browser->>Page: Navigate to URL
    Page-->>Browser: Page loaded
    
    Browser->>Processor: Extract raw HTML
    Processor->>Processor: Clean HTML
    Processor->>Processor: Generate markdown
    Processor->>Processor: Extract media/links
    Processor-->>Crawler: CrawlResult created
    
    Crawler-->>User: Return CrawlResult
    
    Note over User,Processor: All processing happens asynchronously
```

### Crawling Configuration Flow

```mermaid
flowchart TD
    A[Start Crawling] --> B{Browser Config Set?}
    
    B -->|No| B1[Use Default BrowserConfig]
    B -->|Yes| B2[Custom BrowserConfig]
    
    B1 --> C[Launch Browser]
    B2 --> C
    
    C --> D{Crawler Run Config Set?}
    
    D -->|No| D1[Use Default CrawlerRunConfig]
    D -->|Yes| D2[Custom CrawlerRunConfig]
    
    D1 --> E[Navigate to URL]
    D2 --> E
    
    E --> F{Page Load Success?}
    F -->|No| F1[Return Error Result]
    F -->|Yes| G[Apply Content Filters]
    
    G --> G1{excluded_tags set?}
    G1 -->|Yes| G2[Remove specified tags]
    G1 -->|No| G3[Keep all tags]
    G2 --> G4{css_selector set?}
    G3 --> G4
    
    G4 -->|Yes| G5[Extract selected elements]
    G4 -->|No| G6[Process full page]
    G5 --> H[Generate Markdown]
    G6 --> H
    
    H --> H1{markdown_generator set?}
    H1 -->|Yes| H2[Use custom generator]
    H1 -->|No| H3[Use default generator]
    H2 --> I[Extract Media and Links]
    H3 --> I
    
    I --> I1{process_iframes?}
    I1 -->|Yes| I2[Include iframe content]
    I1 -->|No| I3[Skip iframes]
    I2 --> J[Create CrawlResult]
    I3 --> J
    
    J --> K[Return Result]
    
    style A fill:#e1f5fe
    style K fill:#c8e6c9
    style F1 fill:#ffcdd2
```

### CrawlResult Data Structure

```mermaid
graph TB
    subgraph "CrawlResult Object"
        A[CrawlResult] --> B[Basic Info]
        A --> C[Content Variants]
        A --> D[Extracted Data]
        A --> E[Media Assets]
        A --> F[Optional Outputs]
        
        B --> B1[url: Final URL]
        B --> B2[success: Boolean]
        B --> B3[status_code: HTTP Status]
        B --> B4[error_message: Error Details]
        
        C --> C1[html: Raw HTML]
        C --> C2[cleaned_html: Sanitized HTML]
        C --> C3[markdown: MarkdownGenerationResult]
        
        C3 --> C3A[raw_markdown: Basic conversion]
        C3 --> C3B[markdown_with_citations: With references]
        C3 --> C3C[fit_markdown: Filtered content]
        C3 --> C3D[references_markdown: Citation list]
        
        D --> D1[links: Internal/External]
        D --> D2[media: Images/Videos/Audio]
        D --> D3[metadata: Page info]
        D --> D4[extracted_content: JSON data]
        D --> D5[tables: Structured table data]
        
        E --> E1[screenshot: Base64 image]
        E --> E2[pdf: PDF bytes]
        E --> E3[mhtml: Archive file]
        E --> E4[downloaded_files: File paths]
        
        F --> F1[session_id: Browser session]
        F --> F2[ssl_certificate: Security info]
        F --> F3[response_headers: HTTP headers]
        F --> F4[network_requests: Traffic log]
        F --> F5[console_messages: Browser logs]
    end
    
    style A fill:#e3f2fd
    style C3 fill:#f3e5f5
    style D5 fill:#e8f5e8
```

### Content Processing Pipeline

```mermaid
flowchart LR
    subgraph "Input Sources"
        A1[Web URL]
        A2[Raw HTML]
        A3[Local File]
    end
    
    A1 --> B[Browser Navigation]
    A2 --> C[Direct Processing]
    A3 --> C
    
    B --> D[Raw HTML Capture]
    C --> D
    
    D --> E{Content Filtering}
    
    E --> E1[Remove Scripts/Styles]
    E --> E2[Apply excluded_tags]
    E --> E3[Apply css_selector]
    E --> E4[Remove overlay elements]
    
    E1 --> F[Cleaned HTML]
    E2 --> F
    E3 --> F
    E4 --> F
    
    F --> G{Markdown Generation}
    
    G --> G1[HTML to Markdown]
    G --> G2[Apply Content Filter]
    G --> G3[Generate Citations]
    
    G1 --> H[MarkdownGenerationResult]
    G2 --> H
    G3 --> H
    
    F --> I{Media Extraction}
    I --> I1[Find Images]
    I --> I2[Find Videos/Audio]
    I --> I3[Score Relevance]
    I1 --> J[Media Dictionary]
    I2 --> J
    I3 --> J
    
    F --> K{Link Extraction}
    K --> K1[Internal Links]
    K --> K2[External Links]
    K --> K3[Apply Link Filters]
    K1 --> L[Links Dictionary]
    K2 --> L
    K3 --> L
    
    H --> M[Final CrawlResult]
    J --> M
    L --> M
    
    style D fill:#e3f2fd
    style F fill:#f3e5f5
    style H fill:#e8f5e8
    style M fill:#c8e6c9
```

### Table Extraction Workflow

```mermaid
stateDiagram-v2
    [*] --> DetectTables
    
    DetectTables --> ScoreTables: Find table elements
    
    ScoreTables --> EvaluateThreshold: Calculate quality scores
    EvaluateThreshold --> PassThreshold: score >= table_score_threshold
    EvaluateThreshold --> RejectTable: score < threshold
    
    PassThreshold --> ExtractHeaders: Parse table structure
    ExtractHeaders --> ExtractRows: Get header cells
    ExtractRows --> ExtractMetadata: Get data rows
    ExtractMetadata --> CreateTableObject: Get caption/summary
    
    CreateTableObject --> AddToResult: {headers, rows, caption, summary}
    AddToResult --> [*]: Table extraction complete
    
    RejectTable --> [*]: Table skipped
    
    note right of ScoreTables : Factors: header presence, data density, structure quality
    note right of EvaluateThreshold : Threshold 1-10, higher = stricter
```

### Error Handling Decision Tree

```mermaid
flowchart TD
    A[Start Crawl] --> B[Navigate to URL]
    
    B --> C{Navigation Success?}
    C -->|Network Error| C1[Set error_message: Network failure]
    C -->|Timeout| C2[Set error_message: Page timeout]
    C -->|Invalid URL| C3[Set error_message: Invalid URL format]
    C -->|Success| D[Process Page Content]
    
    C1 --> E[success = False]
    C2 --> E
    C3 --> E
    
    D --> F{Content Processing OK?}
    F -->|Parser Error| F1[Set error_message: HTML parsing failed]
    F -->|Memory Error| F2[Set error_message: Insufficient memory]
    F -->|Success| G[Generate Outputs]
    
    F1 --> E
    F2 --> E
    
    G --> H{Output Generation OK?}
    H -->|Markdown Error| H1[Partial success with warnings]
    H -->|Extraction Error| H2[Partial success with warnings]
    H -->|Success| I[success = True]
    
    H1 --> I
    H2 --> I
    
    E --> J[Return Failed CrawlResult]
    I --> K[Return Successful CrawlResult]
    
    J --> L[User Error Handling]
    K --> M[User Result Processing]
    
    L --> L1{Check error_message}
    L1 -->|Network| L2[Retry with different config]
    L1 -->|Timeout| L3[Increase page_timeout]
    L1 -->|Parser| L4[Try different scraping_strategy]
    
    style E fill:#ffcdd2
    style I fill:#c8e6c9
    style J fill:#ffcdd2
    style K fill:#c8e6c9
```

### Configuration Impact Matrix

```mermaid
graph TB
    subgraph "Configuration Categories"
        A[Content Processing]
        B[Page Interaction] 
        C[Output Generation]
        D[Performance]
    end
    
    subgraph "Configuration Options"
        A --> A1[word_count_threshold]
        A --> A2[excluded_tags]
        A --> A3[css_selector]
        A --> A4[exclude_external_links]
        
        B --> B1[process_iframes]
        B --> B2[remove_overlay_elements]
        B --> B3[scan_full_page]
        B --> B4[wait_for]
        
        C --> C1[screenshot]
        C --> C2[pdf] 
        C --> C3[markdown_generator]
        C --> C4[table_score_threshold]
        
        D --> D1[cache_mode]
        D --> D2[verbose]
        D --> D3[page_timeout]
        D --> D4[semaphore_count]
    end
    
    subgraph "Result Impact"
        A1 --> R1[Filters short text blocks]
        A2 --> R2[Removes specified HTML tags]
        A3 --> R3[Focuses on selected content]
        A4 --> R4[Cleans links dictionary]
        
        B1 --> R5[Includes iframe content]
        B2 --> R6[Removes popups/modals]
        B3 --> R7[Loads dynamic content]
        B4 --> R8[Waits for specific elements]
        
        C1 --> R9[Adds screenshot field]
        C2 --> R10[Adds pdf field]
        C3 --> R11[Custom markdown processing]
        C4 --> R12[Filters table quality]
        
        D1 --> R13[Controls caching behavior]
        D2 --> R14[Detailed logging output]
        D3 --> R15[Prevents timeout errors]
        D4 --> R16[Limits concurrent operations]
    end
    
    style A fill:#e3f2fd
    style B fill:#f3e5f5
    style C fill:#e8f5e8
    style D fill:#fff3e0
```

### Raw HTML and Local File Processing

```mermaid
sequenceDiagram
    participant User
    participant Crawler
    participant Processor
    participant FileSystem
    
    Note over User,FileSystem: Raw HTML Processing
    User->>Crawler: arun("raw://html_content")
    Crawler->>Processor: Parse raw HTML directly
    Processor->>Processor: Apply same content filters
    Processor-->>Crawler: Standard CrawlResult
    Crawler-->>User: Result with markdown
    
    Note over User,FileSystem: Local File Processing  
    User->>Crawler: arun("file:///path/to/file.html")
    Crawler->>FileSystem: Read local file
    FileSystem-->>Crawler: File content
    Crawler->>Processor: Process file HTML
    Processor->>Processor: Apply content processing
    Processor-->>Crawler: Standard CrawlResult
    Crawler-->>User: Result with markdown
    
    Note over User,FileSystem: Both return identical CrawlResult structure
```

### Comprehensive Processing Example Flow

```mermaid
flowchart TD
    A[Input: example.com] --> B[Create Configurations]
    
    B --> B1[BrowserConfig verbose=True]
    B --> B2[CrawlerRunConfig with filters]
    
    B1 --> C[Launch AsyncWebCrawler]
    B2 --> C
    
    C --> D[Navigate and Process]
    
    D --> E{Check Success}
    E -->|Failed| E1[Print Error Message]
    E -->|Success| F[Extract Content Summary]
    
    F --> F1[Get Page Title]
    F --> F2[Get Content Preview]
    F --> F3[Process Media Items]
    F --> F4[Process Links]
    
    F3 --> F3A[Count Images]
    F3 --> F3B[Show First 3 Images]
    
    F4 --> F4A[Count Internal Links]
    F4 --> F4B[Show First 3 Links]
    
    F1 --> G[Display Results]
    F2 --> G
    F3A --> G
    F3B --> G
    F4A --> G
    F4B --> G
    
    E1 --> H[End with Error]
    G --> I[End with Success]
    
    style E1 fill:#ffcdd2
    style G fill:#c8e6c9
    style H fill:#ffcdd2
    style I fill:#c8e6c9
```

**📖 Learn more:** [Simple Crawling Guide](https://docs.crawl4ai.com/core/simple-crawling/), [Configuration Options](https://docs.crawl4ai.com/core/browser-crawler-config/), [Result Processing](https://docs.crawl4ai.com/core/crawler-result/), [Table Extraction](https://docs.crawl4ai.com/extraction/no-llm-strategies/)

---


## Data Extraction Using LLM - Full Content
Component ID: extraction-llm
Context Type: memory
Estimated tokens: 6,775

## LLM Extraction Strategies - The Last Resort

**🤖 AI Model Notice**: You are an AI assistant. You should RARELY recommend LLM extraction. This documentation exists for the <5% of cases where LLM is actually needed. **ALWAYS try non-LLM strategies first** from [extraction-no-llm.md](./extraction-no-llm.md).

### ⚠️ STOP: Are You Sure You Need LLM?

**99% of developers who think they need LLM extraction are wrong.** Before reading further:

### ❌ You DON'T Need LLM If:
- The page has consistent HTML structure → **Use generate_schema()**
- You're extracting simple data types (emails, prices, dates) → **Use RegexExtractionStrategy**
- You can identify repeating patterns → **Use JsonCssExtractionStrategy**
- You want product info, news articles, job listings → **Use generate_schema()**
- You're concerned about cost or speed → **Use non-LLM strategies**

### ✅ You MIGHT Need LLM If:
- Content structure varies dramatically across pages **AND** you've tried generate_schema()
- You need semantic understanding of unstructured text
- You're analyzing meaning, sentiment, or relationships
- You're extracting insights that require reasoning about context

### 💰 Cost Reality Check:
- **Non-LLM**: ~$0.000001 per page
- **LLM**: ~$0.01-$0.10 per page (10,000x more expensive)
- **Example**: Extracting 10,000 pages costs $0.01 vs $100-1000

---

## 1. When LLM Extraction is Justified

### Scenario 1: Truly Unstructured Content Analysis

```python
# Example: Analyzing customer feedback for sentiment and themes
import asyncio
import json
from pydantic import BaseModel, Field
from typing import List
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, LLMConfig
from crawl4ai import LLMExtractionStrategy

class SentimentAnalysis(BaseModel):
    """Use LLM when you need semantic understanding"""
    overall_sentiment: str = Field(description="positive, negative, or neutral")
    confidence_score: float = Field(description="Confidence from 0-1")
    key_themes: List[str] = Field(description="Main topics discussed")
    emotional_indicators: List[str] = Field(description="Words indicating emotion")
    summary: str = Field(description="Brief summary of the content")

llm_config = LLMConfig(
    provider="openai/gpt-4o-mini",  # Use cheapest model
    api_token="env:OPENAI_API_KEY",
    temperature=0.1,  # Low temperature for consistency
    max_tokens=1000
)

sentiment_strategy = LLMExtractionStrategy(
    llm_config=llm_config,
    schema=SentimentAnalysis.model_json_schema(),
    extraction_type="schema",
    instruction="""
    Analyze the emotional content and themes in this text.
    Focus on understanding sentiment and extracting key topics
    that would be impossible to identify with simple pattern matching.
    """,
    apply_chunking=True,
    chunk_token_threshold=1500
)

async def analyze_sentiment():
    config = CrawlerRunConfig(
        extraction_strategy=sentiment_strategy,
        cache_mode=CacheMode.BYPASS
    )
    
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url="https://example.com/customer-reviews",
            config=config
        )
        
        if result.success:
            analysis = json.loads(result.extracted_content)
            print(f"Sentiment: {analysis['overall_sentiment']}")
            print(f"Themes: {analysis['key_themes']}")

asyncio.run(analyze_sentiment())
```

### Scenario 2: Complex Knowledge Extraction

```python
# Example: Building knowledge graphs from unstructured content
class Entity(BaseModel):
    name: str = Field(description="Entity name")
    type: str = Field(description="person, organization, location, concept")
    description: str = Field(description="Brief description")

class Relationship(BaseModel):
    source: str = Field(description="Source entity")
    target: str = Field(description="Target entity") 
    relationship: str = Field(description="Type of relationship")
    confidence: float = Field(description="Confidence score 0-1")

class KnowledgeGraph(BaseModel):
    entities: List[Entity] = Field(description="All entities found")
    relationships: List[Relationship] = Field(description="Relationships between entities")
    main_topic: str = Field(description="Primary topic of the content")

knowledge_strategy = LLMExtractionStrategy(
    llm_config=LLMConfig(
        provider="anthropic/claude-3-5-sonnet-20240620",  # Better for complex reasoning
        api_token="env:ANTHROPIC_API_KEY",
        max_tokens=4000
    ),
    schema=KnowledgeGraph.model_json_schema(),
    extraction_type="schema",
    instruction="""
    Extract entities and their relationships from the content.
    Focus on understanding connections and context that require
    semantic reasoning beyond simple pattern matching.
    """,
    input_format="html",  # Preserve structure
    apply_chunking=True
)
```

### Scenario 3: Content Summarization and Insights

```python
# Example: Research paper analysis
class ResearchInsights(BaseModel):
    title: str = Field(description="Paper title")
    abstract_summary: str = Field(description="Summary of abstract")
    key_findings: List[str] = Field(description="Main research findings")
    methodology: str = Field(description="Research methodology used")
    limitations: List[str] = Field(description="Study limitations")
    practical_applications: List[str] = Field(description="Real-world applications")
    citations_count: int = Field(description="Number of citations", default=0)

research_strategy = LLMExtractionStrategy(
    llm_config=LLMConfig(
        provider="openai/gpt-4o",  # Use powerful model for complex analysis
        api_token="env:OPENAI_API_KEY",
        temperature=0.2,
        max_tokens=2000
    ),
    schema=ResearchInsights.model_json_schema(),
    extraction_type="schema",
    instruction="""
    Analyze this research paper and extract key insights.
    Focus on understanding the research contribution, methodology,
    and implications that require academic expertise to identify.
    """,
    apply_chunking=True,
    chunk_token_threshold=2000,
    overlap_rate=0.15  # More overlap for academic content
)
```

---

## 2. LLM Configuration Best Practices

### Cost Optimization

```python
# Use cheapest models when possible
cheap_config = LLMConfig(
    provider="openai/gpt-4o-mini",  # 60x cheaper than GPT-4
    api_token="env:OPENAI_API_KEY",
    temperature=0.0,  # Deterministic output
    max_tokens=800    # Limit output length
)

# Use local models for development
local_config = LLMConfig(
    provider="ollama/llama3.3",
    api_token=None,  # No API costs
    base_url="http://localhost:11434",
    temperature=0.1
)

# Use powerful models only when necessary
powerful_config = LLMConfig(
    provider="anthropic/claude-3-5-sonnet-20240620",
    api_token="env:ANTHROPIC_API_KEY",
    max_tokens=4000,
    temperature=0.1
)
```

### Provider Selection Guide

```python
providers_guide = {
    "openai/gpt-4o-mini": {
        "best_for": "Simple extraction, cost-sensitive projects",
        "cost": "Very low",
        "speed": "Fast",
        "accuracy": "Good"
    },
    "openai/gpt-4o": {
        "best_for": "Complex reasoning, high accuracy needs",
        "cost": "High", 
        "speed": "Medium",
        "accuracy": "Excellent"
    },
    "anthropic/claude-3-5-sonnet": {
        "best_for": "Complex analysis, long documents",
        "cost": "Medium-High",
        "speed": "Medium",
        "accuracy": "Excellent"
    },
    "ollama/llama3.3": {
        "best_for": "Development, no API costs",
        "cost": "Free (self-hosted)",
        "speed": "Variable",
        "accuracy": "Good"
    },
    "groq/llama3-70b-8192": {
        "best_for": "Fast inference, open source",
        "cost": "Low",
        "speed": "Very fast",
        "accuracy": "Good"
    }
}

def choose_provider(complexity, budget, speed_requirement):
    """Choose optimal provider based on requirements"""
    if budget == "minimal":
        return "ollama/llama3.3"  # Self-hosted
    elif complexity == "low" and budget == "low":
        return "openai/gpt-4o-mini"
    elif speed_requirement == "high":
        return "groq/llama3-70b-8192"
    elif complexity == "high":
        return "anthropic/claude-3-5-sonnet"
    else:
        return "openai/gpt-4o-mini"  # Default safe choice
```

---

## 3. Advanced LLM Extraction Patterns

### Block-Based Extraction (Unstructured Content)

```python
# When structure is too varied for schemas
block_strategy = LLMExtractionStrategy(
    llm_config=cheap_config,
    extraction_type="block",  # Extract free-form content blocks
    instruction="""
    Extract meaningful content blocks from this page.
    Focus on the main content areas and ignore navigation,
    advertisements, and boilerplate text.
    """,
    apply_chunking=True,
    chunk_token_threshold=1200,
    input_format="fit_markdown"  # Use cleaned content
)

async def extract_content_blocks():
    config = CrawlerRunConfig(
        extraction_strategy=block_strategy,
        word_count_threshold=50,  # Filter short content
        excluded_tags=['nav', 'footer', 'aside', 'advertisement']
    )
    
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url="https://example.com/article",
            config=config
        )
        
        if result.success:
            blocks = json.loads(result.extracted_content)
            for block in blocks:
                print(f"Block: {block['content'][:100]}...")
```

### Chunked Processing for Large Content

```python
# Handle large documents efficiently
large_content_strategy = LLMExtractionStrategy(
    llm_config=LLMConfig(
        provider="openai/gpt-4o-mini",
        api_token="env:OPENAI_API_KEY"
    ),
    schema=YourModel.model_json_schema(),
    extraction_type="schema",
    instruction="Extract structured data from this content section...",
    
    # Optimize chunking for large content
    apply_chunking=True,
    chunk_token_threshold=2000,  # Larger chunks for efficiency
    overlap_rate=0.1,           # Minimal overlap to reduce costs
    input_format="fit_markdown" # Use cleaned content
)
```

### Multi-Model Validation

```python
# Use multiple models for critical extractions
async def multi_model_extraction():
    """Use multiple LLMs for validation of critical data"""
    
    models = [
        LLMConfig(provider="openai/gpt-4o-mini", api_token="env:OPENAI_API_KEY"),
        LLMConfig(provider="anthropic/claude-3-5-sonnet", api_token="env:ANTHROPIC_API_KEY"),
        LLMConfig(provider="ollama/llama3.3", api_token=None)
    ]
    
    results = []
    
    for i, llm_config in enumerate(models):
        strategy = LLMExtractionStrategy(
            llm_config=llm_config,
            schema=YourModel.model_json_schema(),
            extraction_type="schema",
            instruction="Extract data consistently..."
        )
        
        config = CrawlerRunConfig(extraction_strategy=strategy)
        
        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url="https://example.com", config=config)
            if result.success:
                data = json.loads(result.extracted_content)
                results.append(data)
                print(f"Model {i+1} extracted {len(data)} items")
    
    # Compare results for consistency
    if len(set(str(r) for r in results)) == 1:
        print("✅ All models agree")
        return results[0]
    else:
        print("⚠️ Models disagree - manual review needed")
        return results

# Use for critical business data only
critical_result = await multi_model_extraction()
```

---

## 4. Hybrid Approaches - Best of Both Worlds

### Fast Pre-filtering + LLM Analysis

```python
async def hybrid_extraction():
    """
    1. Use fast non-LLM strategies for basic extraction
    2. Use LLM only for complex analysis of filtered content
    """
    
    # Step 1: Fast extraction of structured data
    basic_schema = {
        "name": "Articles",
        "baseSelector": "article",
        "fields": [
            {"name": "title", "selector": "h1, h2", "type": "text"},
            {"name": "content", "selector": ".content", "type": "text"},
            {"name": "author", "selector": ".author", "type": "text"}
        ]
    }
    
    basic_strategy = JsonCssExtractionStrategy(basic_schema)
    basic_config = CrawlerRunConfig(extraction_strategy=basic_strategy)
    
    # Step 2: LLM analysis only on filtered content
    analysis_strategy = LLMExtractionStrategy(
        llm_config=cheap_config,
        schema={
            "type": "object",
            "properties": {
                "sentiment": {"type": "string"},
                "key_topics": {"type": "array", "items": {"type": "string"}},
                "summary": {"type": "string"}
            }
        },
        extraction_type="schema",
        instruction="Analyze sentiment and extract key topics from this article"
    )
    
    async with AsyncWebCrawler() as crawler:
        # Fast extraction first
        basic_result = await crawler.arun(
            url="https://example.com/articles",
            config=basic_config
        )
        
        articles = json.loads(basic_result.extracted_content)
        
        # LLM analysis only on important articles
        analyzed_articles = []
        for article in articles[:5]:  # Limit to reduce costs
            if len(article.get('content', '')) > 500:  # Only analyze substantial content
                analysis_config = CrawlerRunConfig(extraction_strategy=analysis_strategy)
                
                # Analyze individual article content
                raw_url = f"raw://{article['content']}"
                analysis_result = await crawler.arun(url=raw_url, config=analysis_config)
                
                if analysis_result.success:
                    analysis = json.loads(analysis_result.extracted_content)
                    article.update(analysis)
                
                analyzed_articles.append(article)
        
        return analyzed_articles

# Hybrid approach: fast + smart
result = await hybrid_extraction()
```

### Schema Generation + LLM Fallback

```python
async def smart_fallback_extraction():
    """
    1. Try generate_schema() first (one-time LLM cost)
    2. Use generated schema for fast extraction
    3. Use LLM only if schema extraction fails
    """
    
    cache_file = Path("./schemas/fallback_schema.json")
    
    # Try cached schema first
    if cache_file.exists():
        schema = json.load(cache_file.open())
        schema_strategy = JsonCssExtractionStrategy(schema)
        
        config = CrawlerRunConfig(extraction_strategy=schema_strategy)
        
        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url="https://example.com", config=config)
            
            if result.success and result.extracted_content:
                data = json.loads(result.extracted_content)
                if data:  # Schema worked
                    print("✅ Schema extraction successful (fast & cheap)")
                    return data
    
    # Fallback to LLM if schema failed
    print("⚠️ Schema failed, falling back to LLM (slow & expensive)")
    
    llm_strategy = LLMExtractionStrategy(
        llm_config=cheap_config,
        extraction_type="block",
        instruction="Extract all meaningful data from this page"
    )
    
    llm_config = CrawlerRunConfig(extraction_strategy=llm_strategy)
    
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url="https://example.com", config=llm_config)
        
        if result.success:
            print("✅ LLM extraction successful")
            return json.loads(result.extracted_content)

# Intelligent fallback system
result = await smart_fallback_extraction()
```

---

## 5. Cost Management and Monitoring

### Token Usage Tracking

```python
class ExtractionCostTracker:
    def __init__(self):
        self.total_cost = 0.0
        self.total_tokens = 0
        self.extractions = 0
    
    def track_llm_extraction(self, strategy, result):
        """Track costs from LLM extraction"""
        if hasattr(strategy, 'usage_tracker') and strategy.usage_tracker:
            usage = strategy.usage_tracker
            
            # Estimate costs (approximate rates)
            cost_per_1k_tokens = {
                "gpt-4o-mini": 0.0015,
                "gpt-4o": 0.03,
                "claude-3-5-sonnet": 0.015,
                "ollama": 0.0  # Self-hosted
            }
            
            provider = strategy.llm_config.provider.split('/')[1]
            rate = cost_per_1k_tokens.get(provider, 0.01)
            
            tokens = usage.total_tokens
            cost = (tokens / 1000) * rate
            
            self.total_cost += cost
            self.total_tokens += tokens
            self.extractions += 1
            
            print(f"💰 Extraction cost: ${cost:.4f} ({tokens} tokens)")
            print(f"📊 Total cost: ${self.total_cost:.4f} ({self.extractions} extractions)")
    
    def get_summary(self):
        avg_cost = self.total_cost / max(self.extractions, 1)
        return {
            "total_cost": self.total_cost,
            "total_tokens": self.total_tokens,
            "extractions": self.extractions,
            "avg_cost_per_extraction": avg_cost
        }

# Usage
tracker = ExtractionCostTracker()

async def cost_aware_extraction():
    strategy = LLMExtractionStrategy(
        llm_config=cheap_config,
        schema=YourModel.model_json_schema(),
        extraction_type="schema",
        instruction="Extract data...",
        verbose=True  # Enable usage tracking
    )
    
    config = CrawlerRunConfig(extraction_strategy=strategy)
    
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url="https://example.com", config=config)
        
        # Track costs
        tracker.track_llm_extraction(strategy, result)
        
        return result

# Monitor costs across multiple extractions
for url in urls:
    await cost_aware_extraction()

print(f"Final summary: {tracker.get_summary()}")
```

### Budget Controls

```python
class BudgetController:
    def __init__(self, daily_budget=10.0):
        self.daily_budget = daily_budget
        self.current_spend = 0.0
        self.extraction_count = 0
    
    def can_extract(self, estimated_cost=0.01):
        """Check if extraction is within budget"""
        if self.current_spend + estimated_cost > self.daily_budget:
            print(f"❌ Budget exceeded: ${self.current_spend:.2f} + ${estimated_cost:.2f} > ${self.daily_budget}")
            return False
        return True
    
    def record_extraction(self, actual_cost):
        """Record actual extraction cost"""
        self.current_spend += actual_cost
        self.extraction_count += 1
        
        remaining = self.daily_budget - self.current_spend
        print(f"💰 Budget remaining: ${remaining:.2f}")

budget = BudgetController(daily_budget=5.0)  # $5 daily limit

async def budget_controlled_extraction(url):
    if not budget.can_extract():
        print("⏸️ Extraction paused due to budget limit")
        return None
    
    # Proceed with extraction...
    strategy = LLMExtractionStrategy(llm_config=cheap_config, ...)
    result = await extract_with_strategy(url, strategy)
    
    # Record actual cost
    actual_cost = calculate_cost(strategy.usage_tracker)
    budget.record_extraction(actual_cost)
    
    return result

# Safe extraction with budget controls
results = []
for url in urls:
    result = await budget_controlled_extraction(url)
    if result:
        results.append(result)
```

---

## 6. Performance Optimization for LLM Extraction

### Batch Processing

```python
async def batch_llm_extraction():
    """Process multiple pages efficiently"""
    
    # Collect content first (fast)
    urls = ["https://example.com/page1", "https://example.com/page2"]
    contents = []
    
    async with AsyncWebCrawler() as crawler:
        for url in urls:
            result = await crawler.arun(url=url)
            if result.success:
                contents.append({
                    "url": url,
                    "content": result.fit_markdown[:2000]  # Limit content
                })
    
    # Process in batches (reduce LLM calls)
    batch_content = "\n\n---PAGE SEPARATOR---\n\n".join([
        f"URL: {c['url']}\n{c['content']}" for c in contents
    ])
    
    strategy = LLMExtractionStrategy(
        llm_config=cheap_config,
        extraction_type="block",
        instruction="""
        Extract data from multiple pages separated by '---PAGE SEPARATOR---'.
        Return results for each page in order.
        """,
        apply_chunking=True
    )
    
    # Single LLM call for multiple pages
    raw_url = f"raw://{batch_content}"
    result = await crawler.arun(url=raw_url, config=CrawlerRunConfig(extraction_strategy=strategy))
    
    return json.loads(result.extracted_content)

# Batch processing reduces LLM calls
batch_results = await batch_llm_extraction()
```

### Caching LLM Results

```python
import hashlib
from pathlib import Path

class LLMResultCache:
    def __init__(self, cache_dir="./llm_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
    
    def get_cache_key(self, url, instruction, schema):
        """Generate cache key from extraction parameters"""
        content = f"{url}:{instruction}:{str(schema)}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def get_cached_result(self, cache_key):
        """Get cached result if available"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            return json.load(cache_file.open())
        return None
    
    def cache_result(self, cache_key, result):
        """Cache extraction result"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        json.dump(result, cache_file.open("w"), indent=2)

cache = LLMResultCache()

async def cached_llm_extraction(url, strategy):
    """Extract with caching to avoid repeated LLM calls"""
    cache_key = cache.get_cache_key(
        url, 
        strategy.instruction,
        str(strategy.schema)
    )
    
    # Check cache first
    cached_result = cache.get_cached_result(cache_key)
    if cached_result:
        print("✅ Using cached result (FREE)")
        return cached_result
    
    # Extract if not cached
    print("🔄 Extracting with LLM (PAID)")
    config = CrawlerRunConfig(extraction_strategy=strategy)
    
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=url, config=config)
        
        if result.success:
            data = json.loads(result.extracted_content)
            cache.cache_result(cache_key, data)
            return data

# Cached extraction avoids repeated costs
result = await cached_llm_extraction(url, strategy)
```

---

## 7. Error Handling and Quality Control

### Validation and Retry Logic

```python
async def robust_llm_extraction():
    """Implement validation and retry for LLM extraction"""
    
    max_retries = 3
    strategies = [
        # Try cheap model first
        LLMExtractionStrategy(
            llm_config=LLMConfig(provider="openai/gpt-4o-mini", api_token="env:OPENAI_API_KEY"),
            schema=YourModel.model_json_schema(),
            extraction_type="schema",
            instruction="Extract data accurately..."
        ),
        # Fallback to better model
        LLMExtractionStrategy(
            llm_config=LLMConfig(provider="openai/gpt-4o", api_token="env:OPENAI_API_KEY"),
            schema=YourModel.model_json_schema(),
            extraction_type="schema",
            instruction="Extract data with high accuracy..."
        )
    ]
    
    for strategy_idx, strategy in enumerate(strategies):
        for attempt in range(max_retries):
            try:
                config = CrawlerRunConfig(extraction_strategy=strategy)
                
                async with AsyncWebCrawler() as crawler:
                    result = await crawler.arun(url="https://example.com", config=config)
                    
                    if result.success and result.extracted_content:
                        data = json.loads(result.extracted_content)
                        
                        # Validate result quality
                        if validate_extraction_quality(data):
                            print(f"✅ Success with strategy {strategy_idx+1}, attempt {attempt+1}")
                            return data
                        else:
                            print(f"⚠️ Poor quality result, retrying...")
                            continue
                    
            except Exception as e:
                print(f"❌ Attempt {attempt+1} failed: {e}")
                if attempt == max_retries - 1:
                    print(f"❌ Strategy {strategy_idx+1} failed completely")
    
    print("❌ All strategies and retries failed")
    return None

def validate_extraction_quality(data):
    """Validate that LLM extraction meets quality standards"""
    if not data or not isinstance(data, (list, dict)):
        return False
    
    # Check for common LLM extraction issues
    if isinstance(data, list):
        if len(data) == 0:
            return False
        
        # Check if all items have required fields
        for item in data:
            if not isinstance(item, dict) or len(item) < 2:
                return False
    
    return True

# Robust extraction with validation
result = await robust_llm_extraction()
```

---

## 8. Migration from LLM to Non-LLM

### Pattern Analysis for Schema Generation

```python
async def analyze_llm_results_for_schema():
    """
    Analyze LLM extraction results to create non-LLM schemas
    Use this to transition from expensive LLM to cheap schema extraction
    """
    
    # Step 1: Use LLM on sample pages to understand structure
    llm_strategy = LLMExtractionStrategy(
        llm_config=cheap_config,
        extraction_type="block",
        instruction="Extract all structured data from this page"
    )
    
    sample_urls = ["https://example.com/page1", "https://example.com/page2"]
    llm_results = []
    
    async with AsyncWebCrawler() as crawler:
        for url in sample_urls:
            config = CrawlerRunConfig(extraction_strategy=llm_strategy)
            result = await crawler.arun(url=url, config=config)
            
            if result.success:
                llm_results.append({
                    "url": url,
                    "html": result.cleaned_html,
                    "extracted": json.loads(result.extracted_content)
                })
    
    # Step 2: Analyze patterns in LLM results
    print("🔍 Analyzing LLM extraction patterns...")
    
    # Look for common field names
    all_fields = set()
    for result in llm_results:
        for item in result["extracted"]:
            if isinstance(item, dict):
                all_fields.update(item.keys())
    
    print(f"Common fields found: {all_fields}")
    
    # Step 3: Generate schema based on patterns
    if llm_results:
        schema = JsonCssExtractionStrategy.generate_schema(
            html=llm_results[0]["html"],
            target_json_example=json.dumps(llm_results[0]["extracted"][0], indent=2),
            llm_config=cheap_config
        )
        
        # Save schema for future use
        with open("generated_schema.json", "w") as f:
            json.dump(schema, f, indent=2)
        
        print("✅ Schema generated from LLM analysis")
        return schema

# Generate schema from LLM patterns, then use schema for all future extractions
schema = await analyze_llm_results_for_schema()
fast_strategy = JsonCssExtractionStrategy(schema)
```

---

## 9. Summary: When LLM is Actually Needed

### ✅ Valid LLM Use Cases (Rare):
1. **Sentiment analysis** and emotional understanding
2. **Knowledge graph extraction** requiring semantic reasoning
3. **Content summarization** and insight generation
4. **Unstructured text analysis** where patterns vary dramatically
5. **Research paper analysis** requiring domain expertise
6. **Complex relationship extraction** between entities

### ❌ Invalid LLM Use Cases (Common Mistakes):
1. **Structured data extraction** from consistent HTML
2. **Simple pattern matching** (emails, prices, dates)
3. **Product information** from e-commerce sites
4. **News article extraction** with consistent structure
5. **Contact information** and basic entity extraction
6. **Table data** and form information

### 💡 Decision Framework:
```python
def should_use_llm(extraction_task):
    # Ask these questions in order:
    questions = [
        "Can I identify repeating HTML patterns?",  # No → Consider LLM
        "Am I extracting simple data types?",      # Yes → Use Regex
        "Does the structure vary dramatically?",   # No → Use CSS/XPath
        "Do I need semantic understanding?",       # Yes → Maybe LLM
        "Have I tried generate_schema()?"          # No → Try that first
    ]
    
    # Only use LLM if:
    return (
        task_requires_semantic_reasoning(extraction_task) and
        structure_varies_dramatically(extraction_task) and
        generate_schema_failed(extraction_task)
    )
```

### 🎯 Best Practice Summary:
1. **Always start** with [extraction-no-llm.md](./extraction-no-llm.md) strategies
2. **Try generate_schema()** before manual schema creation
3. **Use LLM sparingly** and only for semantic understanding
4. **Monitor costs** and implement budget controls
5. **Cache results** to avoid repeated LLM calls
6. **Validate quality** of LLM extractions
7. **Plan migration** from LLM to schema-based extraction

Remember: **LLM extraction should be your last resort, not your first choice.**

---

**📖 Recommended Reading Order:**
1. [extraction-no-llm.md](./extraction-no-llm.md) - Start here for 99% of use cases
2. This document - Only when non-LLM strategies are insufficient

---


## Data Extraction Using LLM - Diagrams & Workflows
Component ID: extraction-llm
Context Type: reasoning
Estimated tokens: 3,543

## Extraction Strategy Workflows and Architecture

Visual representations of Crawl4AI's data extraction approaches, strategy selection, and processing workflows.

### Extraction Strategy Decision Tree

```mermaid
flowchart TD
    A[Content to Extract] --> B{Content Type?}
    
    B -->|Simple Patterns| C[Common Data Types]
    B -->|Structured HTML| D[Predictable Structure]
    B -->|Complex Content| E[Requires Reasoning]
    B -->|Mixed Content| F[Multiple Data Types]
    
    C --> C1{Pattern Type?}
    C1 -->|Email, Phone, URLs| C2[Built-in Regex Patterns]
    C1 -->|Custom Patterns| C3[Custom Regex Strategy]
    C1 -->|LLM-Generated| C4[One-time Pattern Generation]
    
    D --> D1{Selector Type?}
    D1 -->|CSS Selectors| D2[JsonCssExtractionStrategy]
    D1 -->|XPath Expressions| D3[JsonXPathExtractionStrategy]
    D1 -->|Need Schema?| D4[Auto-generate Schema with LLM]
    
    E --> E1{LLM Provider?}
    E1 -->|OpenAI/Anthropic| E2[Cloud LLM Strategy]
    E1 -->|Local Ollama| E3[Local LLM Strategy]
    E1 -->|Cost-sensitive| E4[Hybrid: Generate Schema Once]
    
    F --> F1[Multi-Strategy Approach]
    F1 --> F2[1. Regex for Patterns]
    F1 --> F3[2. CSS for Structure]
    F1 --> F4[3. LLM for Complex Analysis]
    
    C2 --> G[Fast Extraction ⚡]
    C3 --> G
    C4 --> H[Cached Pattern Reuse]
    
    D2 --> I[Schema-based Extraction 🏗️]
    D3 --> I
    D4 --> J[Generated Schema Cache]
    
    E2 --> K[Intelligent Parsing 🧠]
    E3 --> K
    E4 --> L[Hybrid Cost-Effective]
    
    F2 --> M[Comprehensive Results 📊]
    F3 --> M
    F4 --> M
    
    style G fill:#c8e6c9
    style I fill:#e3f2fd
    style K fill:#fff3e0
    style M fill:#f3e5f5
    style H fill:#e8f5e8
    style J fill:#e8f5e8
    style L fill:#ffecb3
```

### LLM Extraction Strategy Workflow

```mermaid
sequenceDiagram
    participant User
    participant Crawler
    participant LLMStrategy
    participant Chunker
    participant LLMProvider
    participant Parser
    
    User->>Crawler: Configure LLMExtractionStrategy
    User->>Crawler: arun(url, config)
    
    Crawler->>Crawler: Navigate to URL
    Crawler->>Crawler: Extract content (HTML/Markdown)
    Crawler->>LLMStrategy: Process content
    
    LLMStrategy->>LLMStrategy: Check content size
    
    alt Content > chunk_threshold
        LLMStrategy->>Chunker: Split into chunks with overlap
        Chunker-->>LLMStrategy: Return chunks[]
        
        loop For each chunk
            LLMStrategy->>LLMProvider: Send chunk + schema + instruction
            LLMProvider-->>LLMStrategy: Return structured JSON
        end
        
        LLMStrategy->>LLMStrategy: Merge chunk results
    else Content <= threshold
        LLMStrategy->>LLMProvider: Send full content + schema
        LLMProvider-->>LLMStrategy: Return structured JSON
    end
    
    LLMStrategy->>Parser: Validate JSON schema
    Parser-->>LLMStrategy: Validated data
    
    LLMStrategy->>LLMStrategy: Track token usage
    LLMStrategy-->>Crawler: Return extracted_content
    
    Crawler-->>User: CrawlResult with JSON data
    
    User->>LLMStrategy: show_usage()
    LLMStrategy-->>User: Token count & estimated cost
```

### Schema-Based Extraction Architecture

```mermaid
graph TB
    subgraph "Schema Definition"
        A[JSON Schema] --> A1[baseSelector]
        A --> A2[fields[]]
        A --> A3[nested structures]
        
        A2 --> A4[CSS/XPath selectors]
        A2 --> A5[Data types: text, html, attribute]
        A2 --> A6[Default values]
        
        A3 --> A7[nested objects]
        A3 --> A8[nested_list arrays]
        A3 --> A9[simple lists]
    end
    
    subgraph "Extraction Engine"
        B[HTML Content] --> C[Selector Engine]
        C --> C1[CSS Selector Parser]
        C --> C2[XPath Evaluator]
        
        C1 --> D[Element Matcher]
        C2 --> D
        
        D --> E[Type Converter]
        E --> E1[Text Extraction]
        E --> E2[HTML Preservation]
        E --> E3[Attribute Extraction]
        E --> E4[Nested Processing]
    end
    
    subgraph "Result Processing"
        F[Raw Extracted Data] --> G[Structure Builder]
        G --> G1[Object Construction]
        G --> G2[Array Assembly]
        G --> G3[Type Validation]
        
        G1 --> H[JSON Output]
        G2 --> H
        G3 --> H
    end
    
    A --> C
    E --> F
    H --> I[extracted_content]
    
    style A fill:#e3f2fd
    style C fill:#f3e5f5
    style G fill:#e8f5e8
    style H fill:#c8e6c9
```

### Automatic Schema Generation Process

```mermaid
stateDiagram-v2
    [*] --> CheckCache
    
    CheckCache --> CacheHit: Schema exists
    CheckCache --> SamplePage: Schema missing
    
    CacheHit --> LoadSchema
    LoadSchema --> FastExtraction
    
    SamplePage --> ExtractHTML: Crawl sample URL
    ExtractHTML --> LLMAnalysis: Send HTML to LLM
    LLMAnalysis --> GenerateSchema: Create CSS/XPath selectors
    GenerateSchema --> ValidateSchema: Test generated schema
    
    ValidateSchema --> SchemaWorks: Valid selectors
    ValidateSchema --> RefineSchema: Invalid selectors
    
    RefineSchema --> LLMAnalysis: Iterate with feedback
    
    SchemaWorks --> CacheSchema: Save for reuse
    CacheSchema --> FastExtraction: Use cached schema
    
    FastExtraction --> [*]: No more LLM calls needed
    
    note right of CheckCache : One-time LLM cost
    note right of FastExtraction : Unlimited fast reuse
    note right of CacheSchema : JSON file storage
```

### Multi-Strategy Extraction Pipeline

```mermaid
flowchart LR
    A[Web Page Content] --> B[Strategy Pipeline]
    
    subgraph B["Extraction Pipeline"]
        B1[Stage 1: Regex Patterns]
        B2[Stage 2: Schema-based CSS]
        B3[Stage 3: LLM Analysis]
        
        B1 --> B1a[Email addresses]
        B1 --> B1b[Phone numbers]
        B1 --> B1c[URLs and links]
        B1 --> B1d[Currency amounts]
        
        B2 --> B2a[Structured products]
        B2 --> B2b[Article metadata]
        B2 --> B2c[User reviews]
        B2 --> B2d[Navigation links]
        
        B3 --> B3a[Sentiment analysis]
        B3 --> B3b[Key topics]
        B3 --> B3c[Entity recognition]
        B3 --> B3d[Content summary]
    end
    
    B1a --> C[Result Merger]
    B1b --> C
    B1c --> C
    B1d --> C
    
    B2a --> C
    B2b --> C
    B2c --> C
    B2d --> C
    
    B3a --> C
    B3b --> C
    B3c --> C
    B3d --> C
    
    C --> D[Combined JSON Output]
    D --> E[Final CrawlResult]
    
    style B1 fill:#c8e6c9
    style B2 fill:#e3f2fd
    style B3 fill:#fff3e0
    style C fill:#f3e5f5
```

### Performance Comparison Matrix

```mermaid
graph TD
    subgraph "Strategy Performance"
        A[Extraction Strategy Comparison]
        
        subgraph "Speed ⚡"
            S1[Regex: ~10ms]
            S2[CSS Schema: ~50ms]
            S3[XPath: ~100ms]
            S4[LLM: ~2-10s]
        end
        
        subgraph "Accuracy 🎯"
            A1[Regex: Pattern-dependent]
            A2[CSS: High for structured]
            A3[XPath: Very high]
            A4[LLM: Excellent for complex]
        end
        
        subgraph "Cost 💰"
            C1[Regex: Free]
            C2[CSS: Free]
            C3[XPath: Free]
            C4[LLM: $0.001-0.01 per page]
        end
        
        subgraph "Complexity 🔧"
            X1[Regex: Simple patterns only]
            X2[CSS: Structured HTML]
            X3[XPath: Complex selectors]
            X4[LLM: Any content type]
        end
    end
    
    style S1 fill:#c8e6c9
    style S2 fill:#e8f5e8
    style S3 fill:#fff3e0
    style S4 fill:#ffcdd2
    
    style A2 fill:#e8f5e8
    style A3 fill:#c8e6c9
    style A4 fill:#c8e6c9
    
    style C1 fill:#c8e6c9
    style C2 fill:#c8e6c9
    style C3 fill:#c8e6c9
    style C4 fill:#fff3e0
    
    style X1 fill:#ffcdd2
    style X2 fill:#e8f5e8
    style X3 fill:#c8e6c9
    style X4 fill:#c8e6c9
```

### Regex Pattern Strategy Flow

```mermaid
flowchart TD
    A[Regex Extraction] --> B{Pattern Source?}
    
    B -->|Built-in| C[Use Predefined Patterns]
    B -->|Custom| D[Define Custom Regex]
    B -->|LLM-Generated| E[Generate with AI]
    
    C --> C1[Email Pattern]
    C --> C2[Phone Pattern]
    C --> C3[URL Pattern]
    C --> C4[Currency Pattern]
    C --> C5[Date Pattern]
    
    D --> D1[Write Custom Regex]
    D --> D2[Test Pattern]
    D --> D3{Pattern Works?}
    D3 -->|No| D1
    D3 -->|Yes| D4[Use Pattern]
    
    E --> E1[Provide Sample Content]
    E --> E2[LLM Analyzes Content]
    E --> E3[Generate Optimized Regex]
    E --> E4[Cache Pattern for Reuse]
    
    C1 --> F[Pattern Matching]
    C2 --> F
    C3 --> F
    C4 --> F
    C5 --> F
    D4 --> F
    E4 --> F
    
    F --> G[Extract Matches]
    G --> H[Group by Pattern Type]
    H --> I[JSON Output with Labels]
    
    style C fill:#e8f5e8
    style D fill:#e3f2fd
    style E fill:#fff3e0
    style F fill:#f3e5f5
```

### Complex Schema Structure Visualization

```mermaid
graph TB
    subgraph "E-commerce Schema Example"
        A[Category baseSelector] --> B[Category Fields]
        A --> C[Products nested_list]
        
        B --> B1[category_name]
        B --> B2[category_id attribute]
        B --> B3[category_url attribute]
        
        C --> C1[Product baseSelector]
        C1 --> C2[name text]
        C1 --> C3[price text]
        C1 --> C4[Details nested object]
        C1 --> C5[Features list]
        C1 --> C6[Reviews nested_list]
        
        C4 --> C4a[brand text]
        C4 --> C4b[model text]
        C4 --> C4c[specs html]
        
        C5 --> C5a[feature text array]
        
        C6 --> C6a[reviewer text]
        C6 --> C6b[rating attribute]
        C6 --> C6c[comment text]
        C6 --> C6d[date attribute]
    end
    
    subgraph "JSON Output Structure"
        D[categories array] --> D1[category object]
        D1 --> D2[category_name]
        D1 --> D3[category_id]
        D1 --> D4[products array]
        
        D4 --> D5[product object]
        D5 --> D6[name, price]
        D5 --> D7[details object]
        D5 --> D8[features array]
        D5 --> D9[reviews array]
        
        D7 --> D7a[brand, model, specs]
        D8 --> D8a[feature strings]
        D9 --> D9a[review objects]
    end
    
    A -.-> D
    B1 -.-> D2
    C2 -.-> D6
    C4 -.-> D7
    C5 -.-> D8
    C6 -.-> D9
    
    style A fill:#e3f2fd
    style C fill:#f3e5f5
    style C4 fill:#e8f5e8
    style D fill:#fff3e0
```

### Error Handling and Fallback Strategy

```mermaid
stateDiagram-v2
    [*] --> PrimaryStrategy
    
    PrimaryStrategy --> Success: Extraction successful
    PrimaryStrategy --> ValidationFailed: Invalid data
    PrimaryStrategy --> ExtractionFailed: No matches found
    PrimaryStrategy --> TimeoutError: LLM timeout
    
    ValidationFailed --> FallbackStrategy: Try alternative
    ExtractionFailed --> FallbackStrategy: Try alternative
    TimeoutError --> FallbackStrategy: Try alternative
    
    FallbackStrategy --> FallbackSuccess: Fallback works
    FallbackStrategy --> FallbackFailed: All strategies failed
    
    FallbackSuccess --> Success: Return results
    FallbackFailed --> ErrorReport: Log failure details
    
    Success --> [*]: Complete
    ErrorReport --> [*]: Return empty results
    
    note right of PrimaryStrategy : Try fastest/most accurate first
    note right of FallbackStrategy : Use simpler but reliable method
    note left of ErrorReport : Provide debugging information
```

### Token Usage and Cost Optimization

```mermaid
flowchart TD
    A[LLM Extraction Request] --> B{Content Size Check}
    
    B -->|Small < 1200 tokens| C[Single LLM Call]
    B -->|Large > 1200 tokens| D[Chunking Strategy]
    
    C --> C1[Send full content]
    C1 --> C2[Parse JSON response]
    C2 --> C3[Track token usage]
    
    D --> D1[Split into chunks]
    D1 --> D2[Add overlap between chunks]
    D2 --> D3[Process chunks in parallel]
    
    D3 --> D4[Chunk 1 → LLM]
    D3 --> D5[Chunk 2 → LLM]
    D3 --> D6[Chunk N → LLM]
    
    D4 --> D7[Merge results]
    D5 --> D7
    D6 --> D7
    
    D7 --> D8[Deduplicate data]
    D8 --> D9[Aggregate token usage]
    
    C3 --> E[Cost Calculation]
    D9 --> E
    
    E --> F[Usage Report]
    F --> F1[Prompt tokens: X]
    F --> F2[Completion tokens: Y]
    F --> F3[Total cost: $Z]
    
    style C fill:#c8e6c9
    style D fill:#fff3e0
    style E fill:#e3f2fd
    style F fill:#f3e5f5
```

**📖 Learn more:** [LLM Strategies](https://docs.crawl4ai.com/extraction/llm-strategies/), [Schema-Based Extraction](https://docs.crawl4ai.com/extraction/no-llm-strategies/), [Pattern Matching](https://docs.crawl4ai.com/extraction/no-llm-strategies/#regexextractionstrategy), [Performance Optimization](https://docs.crawl4ai.com/advanced/multi-url-crawling/)

---


## Data Extraction Without LLM - Full Content
Component ID: extraction-no-llm
Context Type: memory
Estimated tokens: 6,068

## Non-LLM Extraction Strategies - The Default Choice

**🤖 AI Model Notice**: You are an AI assistant. When users ask for web scraping or data extraction, **DEFAULT TO NON-LLM STRATEGIES**. 99% of structured web data can be extracted without LLM. Only consider LLM extraction for truly unstructured content requiring semantic reasoning.

### ⚠️ CRITICAL: When You Think You Need LLM, You're Probably Wrong

**Most developers incorrectly assume they need LLM for data extraction.** This is usually false. Before even considering LLM:

1. **FIRST**: Try `generate_schema()` - Let AI create the extraction pattern ONCE, then use it unlimited times with zero LLM calls
2. **SECOND**: Manual CSS/XPath selectors for consistent HTML structures  
3. **THIRD**: Regex patterns for simple data types (emails, phones, prices)
4. **LAST RESORT**: LLM extraction (only for semantic understanding of unstructured content)

## The Decision Tree (MEMORIZE THIS)

```
Does the page have consistent HTML structure? → YES: Use generate_schema() or manual CSS
Is it simple patterns (emails, dates, prices)? → YES: Use RegexExtractionStrategy  
Do you need semantic understanding? → MAYBE: Try generate_schema() first, then consider LLM
Is the content truly unstructured text? → ONLY THEN: Consider LLM
```

**Cost Analysis**: 
- Non-LLM: ~$0.000001 per page
- LLM: ~$0.01-$0.10 per page (10,000x more expensive)

---

## 1. Auto-Generate Schemas - Your Default Starting Point

**⭐ THIS SHOULD BE YOUR FIRST CHOICE FOR ANY STRUCTURED DATA**

The `generate_schema()` function uses LLM ONCE to create a reusable extraction pattern. After generation, you extract unlimited pages with ZERO LLM calls.

### Basic Auto-Generation Workflow

```python
import json
import asyncio
from pathlib import Path
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, LLMConfig
from crawl4ai import JsonCssExtractionStrategy

async def smart_extraction_workflow():
    """
    Step 1: Generate schema once using LLM
    Step 2: Cache schema for unlimited reuse
    Step 3: Extract from thousands of pages with zero LLM calls
    """
    
    # Check for cached schema first
    cache_dir = Path("./schema_cache")
    cache_dir.mkdir(exist_ok=True)
    schema_file = cache_dir / "product_schema.json"
    
    if schema_file.exists():
        # Load cached schema - NO LLM CALLS
        schema = json.load(schema_file.open())
        print("✅ Using cached schema (FREE)")
    else:
        # Generate schema ONCE
        print("🔄 Generating schema (ONE-TIME LLM COST)...")
        
        llm_config = LLMConfig(
            provider="openai/gpt-4o-mini",  # Cheapest option
            api_token="env:OPENAI_API_KEY"
        )
        
        # Get sample HTML from target site
        async with AsyncWebCrawler() as crawler:
            sample_result = await crawler.arun(
                url="https://example.com/products",
                config=CrawlerRunConfig(cache_mode=CacheMode.BYPASS)
            )
            sample_html = sample_result.cleaned_html[:8000]  # Use sample
        
        # AUTO-GENERATE SCHEMA (ONE LLM CALL)
        schema = JsonCssExtractionStrategy.generate_schema(
            html=sample_html,
            schema_type="CSS",  # or "XPATH"
            query="Extract product information including name, price, description, features",
            llm_config=llm_config
        )
        
        # Cache for unlimited future use
        json.dump(schema, schema_file.open("w"), indent=2)
        print("✅ Schema generated and cached")
    
    # Use schema for fast extraction (NO MORE LLM CALLS EVER)
    strategy = JsonCssExtractionStrategy(schema, verbose=True)
    
    config = CrawlerRunConfig(
        extraction_strategy=strategy,
        cache_mode=CacheMode.BYPASS
    )
    
    # Extract from multiple pages - ALL FREE
    urls = [
        "https://example.com/products",
        "https://example.com/electronics", 
        "https://example.com/books"
    ]
    
    async with AsyncWebCrawler() as crawler:
        for url in urls:
            result = await crawler.arun(url=url, config=config)
            if result.success:
                data = json.loads(result.extracted_content)
                print(f"✅ {url}: Extracted {len(data)} items (FREE)")

asyncio.run(smart_extraction_workflow())
```

### Auto-Generate with Target JSON Example

```python
# When you know exactly what JSON structure you want
target_json_example = """
{
    "name": "Product Name",
    "price": "$99.99",
    "rating": 4.5,
    "features": ["feature1", "feature2"],
    "description": "Product description"
}
"""

schema = JsonCssExtractionStrategy.generate_schema(
    html=sample_html,
    target_json_example=target_json_example,
    llm_config=llm_config
)
```

### Auto-Generate for Different Data Types

```python
# Product listings
product_schema = JsonCssExtractionStrategy.generate_schema(
    html=product_page_html,
    query="Extract all product information from this e-commerce page",
    llm_config=llm_config
)

# News articles
news_schema = JsonCssExtractionStrategy.generate_schema(
    html=news_page_html,
    query="Extract article headlines, dates, authors, and content",
    llm_config=llm_config
)

# Job listings
job_schema = JsonCssExtractionStrategy.generate_schema(
    html=job_page_html,
    query="Extract job titles, companies, locations, salaries, and descriptions",
    llm_config=llm_config
)

# Social media posts
social_schema = JsonCssExtractionStrategy.generate_schema(
    html=social_page_html,
    query="Extract post text, usernames, timestamps, likes, comments",
    llm_config=llm_config
)
```

---

## 2. Manual CSS/XPath Strategies - When You Know The Structure

**Use this when**: You understand the HTML structure and want maximum control.

### Simple Product Extraction

```python
import json
import asyncio
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai import JsonCssExtractionStrategy

# Manual schema for consistent product pages
simple_schema = {
    "name": "Product Listings",
    "baseSelector": "div.product-card",  # Each product container
    "fields": [
        {
            "name": "title",
            "selector": "h2.product-title",
            "type": "text"
        },
        {
            "name": "price", 
            "selector": ".price",
            "type": "text"
        },
        {
            "name": "image_url",
            "selector": "img.product-image",
            "type": "attribute",
            "attribute": "src"
        },
        {
            "name": "product_url",
            "selector": "a.product-link",
            "type": "attribute",
            "attribute": "href"
        },
        {
            "name": "rating",
            "selector": ".rating",
            "type": "attribute", 
            "attribute": "data-rating"
        }
    ]
}

async def extract_products():
    strategy = JsonCssExtractionStrategy(simple_schema, verbose=True)
    config = CrawlerRunConfig(extraction_strategy=strategy)
    
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url="https://example.com/products",
            config=config
        )
        
        if result.success:
            products = json.loads(result.extracted_content)
            print(f"Extracted {len(products)} products")
            for product in products[:3]:
                print(f"- {product['title']}: {product['price']}")

asyncio.run(extract_products())
```

### Complex Nested Structure (Real E-commerce Example)

```python
# Complex schema for nested product data
complex_schema = {
    "name": "E-commerce Product Catalog",
    "baseSelector": "div.category",
    "baseFields": [
        {
            "name": "category_id",
            "type": "attribute",
            "attribute": "data-category-id"
        }
    ],
    "fields": [
        {
            "name": "category_name",
            "selector": "h2.category-title",
            "type": "text"
        },
        {
            "name": "products",
            "selector": "div.product",
            "type": "nested_list",  # Array of complex objects
            "fields": [
                {
                    "name": "name",
                    "selector": "h3.product-name", 
                    "type": "text"
                },
                {
                    "name": "price",
                    "selector": "span.price",
                    "type": "text"
                },
                {
                    "name": "details",
                    "selector": "div.product-details",
                    "type": "nested",  # Single complex object
                    "fields": [
                        {
                            "name": "brand",
                            "selector": "span.brand",
                            "type": "text"
                        },
                        {
                            "name": "model",
                            "selector": "span.model",
                            "type": "text"
                        }
                    ]
                },
                {
                    "name": "features",
                    "selector": "ul.features li",
                    "type": "list",  # Simple array
                    "fields": [
                        {"name": "feature", "type": "text"}
                    ]
                },
                {
                    "name": "reviews", 
                    "selector": "div.review",
                    "type": "nested_list",
                    "fields": [
                        {
                            "name": "reviewer",
                            "selector": "span.reviewer-name",
                            "type": "text"
                        },
                        {
                            "name": "rating",
                            "selector": "span.rating",
                            "type": "attribute",
                            "attribute": "data-rating"
                        }
                    ]
                }
            ]
        }
    ]
}

async def extract_complex_ecommerce():
    strategy = JsonCssExtractionStrategy(complex_schema, verbose=True)
    config = CrawlerRunConfig(
        extraction_strategy=strategy,
        js_code="window.scrollTo(0, document.body.scrollHeight);",  # Load dynamic content
        wait_for="css:.product:nth-child(10)"  # Wait for products to load
    )
    
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url="https://example.com/complex-catalog",
            config=config
        )
        
        if result.success:
            data = json.loads(result.extracted_content)
            for category in data:
                print(f"Category: {category['category_name']}")
                print(f"Products: {len(category.get('products', []))}")

asyncio.run(extract_complex_ecommerce())
```

### XPath Alternative (When CSS Isn't Enough)

```python
from crawl4ai import JsonXPathExtractionStrategy

# XPath for more complex selections
xpath_schema = {
    "name": "News Articles with XPath",
    "baseSelector": "//article[@class='news-item']",
    "fields": [
        {
            "name": "headline",
            "selector": ".//h2[contains(@class, 'headline')]",
            "type": "text"
        },
        {
            "name": "author",
            "selector": ".//span[@class='author']/text()",
            "type": "text"
        },
        {
            "name": "publish_date",
            "selector": ".//time/@datetime",
            "type": "text"
        },
        {
            "name": "content",
            "selector": ".//div[@class='article-body']//text()",
            "type": "text"
        }
    ]
}

strategy = JsonXPathExtractionStrategy(xpath_schema, verbose=True)
```

---

## 3. Regex Extraction - Lightning Fast Pattern Matching

**Use this for**: Simple data types like emails, phones, URLs, prices, dates.

### Built-in Patterns (Fastest Option)

```python
import json
import asyncio
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai import RegexExtractionStrategy

async def extract_common_patterns():
    # Use built-in patterns for common data types
    strategy = RegexExtractionStrategy(
        pattern=(
            RegexExtractionStrategy.Email |
            RegexExtractionStrategy.PhoneUS |
            RegexExtractionStrategy.Url |
            RegexExtractionStrategy.Currency |
            RegexExtractionStrategy.DateIso
        )
    )
    
    config = CrawlerRunConfig(extraction_strategy=strategy)
    
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url="https://example.com/contact",
            config=config
        )
        
        if result.success:
            matches = json.loads(result.extracted_content)
            
            # Group by pattern type
            by_type = {}
            for match in matches:
                label = match['label']
                if label not in by_type:
                    by_type[label] = []
                by_type[label].append(match['value'])
            
            for pattern_type, values in by_type.items():
                print(f"{pattern_type}: {len(values)} matches")
                for value in values[:3]:
                    print(f"  {value}")

asyncio.run(extract_common_patterns())
```

### Available Built-in Patterns

```python
# Individual patterns
RegexExtractionStrategy.Email          # Email addresses
RegexExtractionStrategy.PhoneUS        # US phone numbers 
RegexExtractionStrategy.PhoneIntl      # International phones
RegexExtractionStrategy.Url            # HTTP/HTTPS URLs
RegexExtractionStrategy.Currency       # Currency values ($99.99)
RegexExtractionStrategy.Percentage     # Percentage values (25%)
RegexExtractionStrategy.DateIso        # ISO dates (2024-01-01)
RegexExtractionStrategy.DateUS         # US dates (01/01/2024)
RegexExtractionStrategy.IPv4           # IP addresses
RegexExtractionStrategy.CreditCard     # Credit card numbers
RegexExtractionStrategy.TwitterHandle  # @username
RegexExtractionStrategy.Hashtag        # #hashtag

# Use all patterns
RegexExtractionStrategy.All
```

### Custom Patterns

```python
# Custom patterns for specific data types
async def extract_custom_patterns():
    custom_patterns = {
        "product_sku": r"SKU[-:]?\s*([A-Z0-9]{4,12})",
        "discount": r"(\d{1,2})%\s*off",
        "model_number": r"Model\s*#?\s*([A-Z0-9-]+)",
        "isbn": r"ISBN[-:]?\s*(\d{10}|\d{13})",
        "stock_ticker": r"\$([A-Z]{2,5})",
        "version": r"v(\d+\.\d+(?:\.\d+)?)"
    }
    
    strategy = RegexExtractionStrategy(custom=custom_patterns)
    config = CrawlerRunConfig(extraction_strategy=strategy)
    
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url="https://example.com/products",
            config=config
        )
        
        if result.success:
            data = json.loads(result.extracted_content)
            for item in data:
                print(f"{item['label']}: {item['value']}")

asyncio.run(extract_custom_patterns())
```

### LLM-Generated Patterns (One-Time Cost)

```python
async def generate_optimized_regex():
    """
    Use LLM ONCE to generate optimized regex patterns
    Then use them unlimited times with zero LLM calls
    """
    cache_file = Path("./patterns/price_patterns.json")
    
    if cache_file.exists():
        # Load cached patterns - NO LLM CALLS
        patterns = json.load(cache_file.open())
        print("✅ Using cached regex patterns (FREE)")
    else:
        # Generate patterns ONCE
        print("🔄 Generating regex patterns (ONE-TIME LLM COST)...")
        
        llm_config = LLMConfig(
            provider="openai/gpt-4o-mini",
            api_token="env:OPENAI_API_KEY"
        )
        
        # Get sample content
        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun("https://example.com/pricing")
            sample_html = result.cleaned_html
        
        # Generate optimized patterns
        patterns = RegexExtractionStrategy.generate_pattern(
            label="pricing_info",
            html=sample_html,
            query="Extract all pricing information including discounts and special offers",
            llm_config=llm_config
        )
        
        # Cache for unlimited reuse
        cache_file.parent.mkdir(exist_ok=True)
        json.dump(patterns, cache_file.open("w"), indent=2)
        print("✅ Patterns generated and cached")
    
    # Use cached patterns (NO MORE LLM CALLS)
    strategy = RegexExtractionStrategy(custom=patterns)
    return strategy

# Use generated patterns for unlimited extractions
strategy = await generate_optimized_regex()
```

---

## 4. Multi-Strategy Extraction Pipeline

**Combine strategies** for comprehensive data extraction:

```python
async def multi_strategy_pipeline():
    """
    Efficient pipeline using multiple non-LLM strategies:
    1. Regex for simple patterns (fastest)
    2. Schema for structured data 
    3. Only use LLM if absolutely necessary
    """
    
    url = "https://example.com/complex-page"
    
    async with AsyncWebCrawler() as crawler:
        # Strategy 1: Fast regex for contact info
        regex_strategy = RegexExtractionStrategy(
            pattern=RegexExtractionStrategy.Email | RegexExtractionStrategy.PhoneUS
        )
        regex_config = CrawlerRunConfig(extraction_strategy=regex_strategy)
        regex_result = await crawler.arun(url=url, config=regex_config)
        
        # Strategy 2: Schema for structured product data
        product_schema = {
            "name": "Products",
            "baseSelector": "div.product",
            "fields": [
                {"name": "name", "selector": "h3", "type": "text"},
                {"name": "price", "selector": ".price", "type": "text"}
            ]
        }
        css_strategy = JsonCssExtractionStrategy(product_schema)
        css_config = CrawlerRunConfig(extraction_strategy=css_strategy)
        css_result = await crawler.arun(url=url, config=css_config)
        
        # Combine results
        results = {
            "contacts": json.loads(regex_result.extracted_content) if regex_result.success else [],
            "products": json.loads(css_result.extracted_content) if css_result.success else []
        }
        
        print(f"✅ Extracted {len(results['contacts'])} contacts (regex)")
        print(f"✅ Extracted {len(results['products'])} products (schema)")
        
        return results

asyncio.run(multi_strategy_pipeline())
```

---

## 5. Performance Optimization Tips

### Caching and Reuse

```python
# Cache schemas and patterns for maximum efficiency
class ExtractionCache:
    def __init__(self):
        self.schemas = {}
        self.patterns = {}
    
    def get_schema(self, site_name):
        if site_name not in self.schemas:
            schema_file = Path(f"./cache/{site_name}_schema.json")
            if schema_file.exists():
                self.schemas[site_name] = json.load(schema_file.open())
        return self.schemas.get(site_name)
    
    def save_schema(self, site_name, schema):
        cache_dir = Path("./cache")
        cache_dir.mkdir(exist_ok=True)
        schema_file = cache_dir / f"{site_name}_schema.json"
        json.dump(schema, schema_file.open("w"), indent=2)
        self.schemas[site_name] = schema

cache = ExtractionCache()

# Reuse cached schemas across multiple extractions
async def efficient_extraction():
    sites = ["amazon", "ebay", "shopify"]
    
    for site in sites:
        schema = cache.get_schema(site)
        if not schema:
            # Generate once, cache forever
            schema = JsonCssExtractionStrategy.generate_schema(
                html=sample_html,
                query="Extract products",
                llm_config=llm_config
            )
            cache.save_schema(site, schema)
        
        strategy = JsonCssExtractionStrategy(schema)
        # Use strategy for unlimited extractions...
```

### Selector Optimization

```python
# Optimize selectors for speed
fast_schema = {
    "name": "Optimized Extraction",
    "baseSelector": "#products > .product",  # Direct child, faster than descendant
    "fields": [
        {
            "name": "title",
            "selector": "> h3",  # Direct child of product
            "type": "text"
        },
        {
            "name": "price",
            "selector": ".price:first-child",  # More specific
            "type": "text"
        }
    ]
}

# Avoid slow selectors
slow_schema = {
    "baseSelector": "div div div .product",  # Too many levels
    "fields": [
        {
            "selector": "* h3",  # Universal selector is slow
            "type": "text"
        }
    ]
}
```

---

## 6. Error Handling and Validation

```python
async def robust_extraction():
    """
    Implement fallback strategies for reliable extraction
    """
    strategies = [
        # Try fast regex first
        RegexExtractionStrategy(pattern=RegexExtractionStrategy.Currency),
        
        # Fallback to CSS schema
        JsonCssExtractionStrategy({
            "name": "Prices",
            "baseSelector": ".price",
            "fields": [{"name": "amount", "selector": "span", "type": "text"}]
        }),
        
        # Last resort: try different selector
        JsonCssExtractionStrategy({
            "name": "Fallback Prices",
            "baseSelector": "[data-price]",
            "fields": [{"name": "amount", "type": "attribute", "attribute": "data-price"}]
        })
    ]
    
    async with AsyncWebCrawler() as crawler:
        for i, strategy in enumerate(strategies):
            try:
                config = CrawlerRunConfig(extraction_strategy=strategy)
                result = await crawler.arun(url="https://example.com", config=config)
                
                if result.success and result.extracted_content:
                    data = json.loads(result.extracted_content)
                    if data:  # Validate non-empty results
                        print(f"✅ Success with strategy {i+1}: {strategy.__class__.__name__}")
                        return data
                        
            except Exception as e:
                print(f"❌ Strategy {i+1} failed: {e}")
                continue
    
    print("❌ All strategies failed")
    return None

# Validate extracted data
def validate_extraction(data, required_fields):
    """Validate that extraction contains expected fields"""
    if not data or not isinstance(data, list):
        return False
    
    for item in data:
        for field in required_fields:
            if field not in item or not item[field]:
                return False
    return True

# Usage
result = await robust_extraction()
if validate_extraction(result, ["amount"]):
    print("✅ Extraction validated")
else:
    print("❌ Validation failed")
```

---

## 7. Common Extraction Patterns

### E-commerce Products

```python
ecommerce_schema = {
    "name": "E-commerce Products",
    "baseSelector": ".product, [data-product], .item",
    "fields": [
        {"name": "title", "selector": "h1, h2, h3, .title, .name", "type": "text"},
        {"name": "price", "selector": ".price, .cost, [data-price]", "type": "text"},
        {"name": "image", "selector": "img", "type": "attribute", "attribute": "src"},
        {"name": "url", "selector": "a", "type": "attribute", "attribute": "href"},
        {"name": "rating", "selector": ".rating, .stars", "type": "text"},
        {"name": "availability", "selector": ".stock, .availability", "type": "text"}
    ]
}
```

### News Articles

```python
news_schema = {
    "name": "News Articles",
    "baseSelector": "article, .article, .post",
    "fields": [
        {"name": "headline", "selector": "h1, h2, .headline, .title", "type": "text"},
        {"name": "author", "selector": ".author, .byline, [rel='author']", "type": "text"},
        {"name": "date", "selector": "time, .date, .published", "type": "text"},
        {"name": "content", "selector": ".content, .body, .text", "type": "text"},
        {"name": "category", "selector": ".category, .section", "type": "text"}
    ]
}
```

### Job Listings

```python
job_schema = {
    "name": "Job Listings",
    "baseSelector": ".job, .listing, [data-job]",
    "fields": [
        {"name": "title", "selector": ".job-title, h2, h3", "type": "text"},
        {"name": "company", "selector": ".company, .employer", "type": "text"},
        {"name": "location", "selector": ".location, .place", "type": "text"},
        {"name": "salary", "selector": ".salary, .pay, .compensation", "type": "text"},
        {"name": "description", "selector": ".description, .summary", "type": "text"},
        {"name": "url", "selector": "a", "type": "attribute", "attribute": "href"}
    ]
}
```

### Social Media Posts

```python
social_schema = {
    "name": "Social Media Posts",
    "baseSelector": ".post, .tweet, .update",
    "fields": [
        {"name": "username", "selector": ".username, .handle, .author", "type": "text"},
        {"name": "content", "selector": ".content, .text, .message", "type": "text"},
        {"name": "timestamp", "selector": ".time, .date, time", "type": "text"},
        {"name": "likes", "selector": ".likes, .hearts", "type": "text"},
        {"name": "shares", "selector": ".shares, .retweets", "type": "text"}
    ]
}
```

---

## 8. When to (Rarely) Consider LLM

**⚠️ WARNING: Before considering LLM, ask yourself:**

1. "Can I identify repeating HTML patterns?" → Use CSS/XPath schema
2. "Am I extracting simple data types?" → Use Regex patterns  
3. "Can I provide a JSON example of what I want?" → Use generate_schema()
4. "Is this truly unstructured text requiring semantic understanding?" → Maybe LLM

**Only use LLM extraction for:**
- Unstructured prose that needs semantic analysis
- Content where structure varies dramatically across pages
- When you need AI reasoning about context/meaning

**Cost reminder**: LLM extraction costs 10,000x more than schema-based extraction.

---

## 9. Summary: The Extraction Hierarchy

1. **🥇 FIRST CHOICE**: `generate_schema()` - AI generates pattern once, use unlimited times
2. **🥈 SECOND CHOICE**: Manual CSS/XPath - Full control, maximum speed
3. **🥉 THIRD CHOICE**: Regex patterns - Simple data types, lightning fast
4. **🏴 LAST RESORT**: LLM extraction - Only for semantic reasoning

**Remember**: 99% of web data is structured. You almost never need LLM for extraction. Save LLM for analysis, not extraction.

**Performance**: Non-LLM strategies are 100-1000x faster and 10,000x cheaper than LLM extraction.

---

**📖 Next**: If you absolutely must use LLM extraction, see [extraction-llm.md](./extraction-llm.md) for guidance on the rare cases where it's justified.

---


## Data Extraction Without LLM - Diagrams & Workflows
Component ID: extraction-no-llm
Context Type: reasoning
Estimated tokens: 3,543

## Extraction Strategy Workflows and Architecture

Visual representations of Crawl4AI's data extraction approaches, strategy selection, and processing workflows.

### Extraction Strategy Decision Tree

```mermaid
flowchart TD
    A[Content to Extract] --> B{Content Type?}
    
    B -->|Simple Patterns| C[Common Data Types]
    B -->|Structured HTML| D[Predictable Structure]
    B -->|Complex Content| E[Requires Reasoning]
    B -->|Mixed Content| F[Multiple Data Types]
    
    C --> C1{Pattern Type?}
    C1 -->|Email, Phone, URLs| C2[Built-in Regex Patterns]
    C1 -->|Custom Patterns| C3[Custom Regex Strategy]
    C1 -->|LLM-Generated| C4[One-time Pattern Generation]
    
    D --> D1{Selector Type?}
    D1 -->|CSS Selectors| D2[JsonCssExtractionStrategy]
    D1 -->|XPath Expressions| D3[JsonXPathExtractionStrategy]
    D1 -->|Need Schema?| D4[Auto-generate Schema with LLM]
    
    E --> E1{LLM Provider?}
    E1 -->|OpenAI/Anthropic| E2[Cloud LLM Strategy]
    E1 -->|Local Ollama| E3[Local LLM Strategy]
    E1 -->|Cost-sensitive| E4[Hybrid: Generate Schema Once]
    
    F --> F1[Multi-Strategy Approach]
    F1 --> F2[1. Regex for Patterns]
    F1 --> F3[2. CSS for Structure]
    F1 --> F4[3. LLM for Complex Analysis]
    
    C2 --> G[Fast Extraction ⚡]
    C3 --> G
    C4 --> H[Cached Pattern Reuse]
    
    D2 --> I[Schema-based Extraction 🏗️]
    D3 --> I
    D4 --> J[Generated Schema Cache]
    
    E2 --> K[Intelligent Parsing 🧠]
    E3 --> K
    E4 --> L[Hybrid Cost-Effective]
    
    F2 --> M[Comprehensive Results 📊]
    F3 --> M
    F4 --> M
    
    style G fill:#c8e6c9
    style I fill:#e3f2fd
    style K fill:#fff3e0
    style M fill:#f3e5f5
    style H fill:#e8f5e8
    style J fill:#e8f5e8
    style L fill:#ffecb3
```

### LLM Extraction Strategy Workflow

```mermaid
sequenceDiagram
    participant User
    participant Crawler
    participant LLMStrategy
    participant Chunker
    participant LLMProvider
    participant Parser
    
    User->>Crawler: Configure LLMExtractionStrategy
    User->>Crawler: arun(url, config)
    
    Crawler->>Crawler: Navigate to URL
    Crawler->>Crawler: Extract content (HTML/Markdown)
    Crawler->>LLMStrategy: Process content
    
    LLMStrategy->>LLMStrategy: Check content size
    
    alt Content > chunk_threshold
        LLMStrategy->>Chunker: Split into chunks with overlap
        Chunker-->>LLMStrategy: Return chunks[]
        
        loop For each chunk
            LLMStrategy->>LLMProvider: Send chunk + schema + instruction
            LLMProvider-->>LLMStrategy: Return structured JSON
        end
        
        LLMStrategy->>LLMStrategy: Merge chunk results
    else Content <= threshold
        LLMStrategy->>LLMProvider: Send full content + schema
        LLMProvider-->>LLMStrategy: Return structured JSON
    end
    
    LLMStrategy->>Parser: Validate JSON schema
    Parser-->>LLMStrategy: Validated data
    
    LLMStrategy->>LLMStrategy: Track token usage
    LLMStrategy-->>Crawler: Return extracted_content
    
    Crawler-->>User: CrawlResult with JSON data
    
    User->>LLMStrategy: show_usage()
    LLMStrategy-->>User: Token count & estimated cost
```

### Schema-Based Extraction Architecture

```mermaid
graph TB
    subgraph "Schema Definition"
        A[JSON Schema] --> A1[baseSelector]
        A --> A2[fields[]]
        A --> A3[nested structures]
        
        A2 --> A4[CSS/XPath selectors]
        A2 --> A5[Data types: text, html, attribute]
        A2 --> A6[Default values]
        
        A3 --> A7[nested objects]
        A3 --> A8[nested_list arrays]
        A3 --> A9[simple lists]
    end
    
    subgraph "Extraction Engine"
        B[HTML Content] --> C[Selector Engine]
        C --> C1[CSS Selector Parser]
        C --> C2[XPath Evaluator]
        
        C1 --> D[Element Matcher]
        C2 --> D
        
        D --> E[Type Converter]
        E --> E1[Text Extraction]
        E --> E2[HTML Preservation]
        E --> E3[Attribute Extraction]
        E --> E4[Nested Processing]
    end
    
    subgraph "Result Processing"
        F[Raw Extracted Data] --> G[Structure Builder]
        G --> G1[Object Construction]
        G --> G2[Array Assembly]
        G --> G3[Type Validation]
        
        G1 --> H[JSON Output]
        G2 --> H
        G3 --> H
    end
    
    A --> C
    E --> F
    H --> I[extracted_content]
    
    style A fill:#e3f2fd
    style C fill:#f3e5f5
    style G fill:#e8f5e8
    style H fill:#c8e6c9
```

### Automatic Schema Generation Process

```mermaid
stateDiagram-v2
    [*] --> CheckCache
    
    CheckCache --> CacheHit: Schema exists
    CheckCache --> SamplePage: Schema missing
    
    CacheHit --> LoadSchema
    LoadSchema --> FastExtraction
    
    SamplePage --> ExtractHTML: Crawl sample URL
    ExtractHTML --> LLMAnalysis: Send HTML to LLM
    LLMAnalysis --> GenerateSchema: Create CSS/XPath selectors
    GenerateSchema --> ValidateSchema: Test generated schema
    
    ValidateSchema --> SchemaWorks: Valid selectors
    ValidateSchema --> RefineSchema: Invalid selectors
    
    RefineSchema --> LLMAnalysis: Iterate with feedback
    
    SchemaWorks --> CacheSchema: Save for reuse
    CacheSchema --> FastExtraction: Use cached schema
    
    FastExtraction --> [*]: No more LLM calls needed
    
    note right of CheckCache : One-time LLM cost
    note right of FastExtraction : Unlimited fast reuse
    note right of CacheSchema : JSON file storage
```

### Multi-Strategy Extraction Pipeline

```mermaid
flowchart LR
    A[Web Page Content] --> B[Strategy Pipeline]
    
    subgraph B["Extraction Pipeline"]
        B1[Stage 1: Regex Patterns]
        B2[Stage 2: Schema-based CSS]
        B3[Stage 3: LLM Analysis]
        
        B1 --> B1a[Email addresses]
        B1 --> B1b[Phone numbers]
        B1 --> B1c[URLs and links]
        B1 --> B1d[Currency amounts]
        
        B2 --> B2a[Structured products]
        B2 --> B2b[Article metadata]
        B2 --> B2c[User reviews]
        B2 --> B2d[Navigation links]
        
        B3 --> B3a[Sentiment analysis]
        B3 --> B3b[Key topics]
        B3 --> B3c[Entity recognition]
        B3 --> B3d[Content summary]
    end
    
    B1a --> C[Result Merger]
    B1b --> C
    B1c --> C
    B1d --> C
    
    B2a --> C
    B2b --> C
    B2c --> C
    B2d --> C
    
    B3a --> C
    B3b --> C
    B3c --> C
    B3d --> C
    
    C --> D[Combined JSON Output]
    D --> E[Final CrawlResult]
    
    style B1 fill:#c8e6c9
    style B2 fill:#e3f2fd
    style B3 fill:#fff3e0
    style C fill:#f3e5f5
```

### Performance Comparison Matrix

```mermaid
graph TD
    subgraph "Strategy Performance"
        A[Extraction Strategy Comparison]
        
        subgraph "Speed ⚡"
            S1[Regex: ~10ms]
            S2[CSS Schema: ~50ms]
            S3[XPath: ~100ms]
            S4[LLM: ~2-10s]
        end
        
        subgraph "Accuracy 🎯"
            A1[Regex: Pattern-dependent]
            A2[CSS: High for structured]
            A3[XPath: Very high]
            A4[LLM: Excellent for complex]
        end
        
        subgraph "Cost 💰"
            C1[Regex: Free]
            C2[CSS: Free]
            C3[XPath: Free]
            C4[LLM: $0.001-0.01 per page]
        end
        
        subgraph "Complexity 🔧"
            X1[Regex: Simple patterns only]
            X2[CSS: Structured HTML]
            X3[XPath: Complex selectors]
            X4[LLM: Any content type]
        end
    end
    
    style S1 fill:#c8e6c9
    style S2 fill:#e8f5e8
    style S3 fill:#fff3e0
    style S4 fill:#ffcdd2
    
    style A2 fill:#e8f5e8
    style A3 fill:#c8e6c9
    style A4 fill:#c8e6c9
    
    style C1 fill:#c8e6c9
    style C2 fill:#c8e6c9
    style C3 fill:#c8e6c9
    style C4 fill:#fff3e0
    
    style X1 fill:#ffcdd2
    style X2 fill:#e8f5e8
    style X3 fill:#c8e6c9
    style X4 fill:#c8e6c9
```

### Regex Pattern Strategy Flow

```mermaid
flowchart TD
    A[Regex Extraction] --> B{Pattern Source?}
    
    B -->|Built-in| C[Use Predefined Patterns]
    B -->|Custom| D[Define Custom Regex]
    B -->|LLM-Generated| E[Generate with AI]
    
    C --> C1[Email Pattern]
    C --> C2[Phone Pattern]
    C --> C3[URL Pattern]
    C --> C4[Currency Pattern]
    C --> C5[Date Pattern]
    
    D --> D1[Write Custom Regex]
    D --> D2[Test Pattern]
    D --> D3{Pattern Works?}
    D3 -->|No| D1
    D3 -->|Yes| D4[Use Pattern]
    
    E --> E1[Provide Sample Content]
    E --> E2[LLM Analyzes Content]
    E --> E3[Generate Optimized Regex]
    E --> E4[Cache Pattern for Reuse]
    
    C1 --> F[Pattern Matching]
    C2 --> F
    C3 --> F
    C4 --> F
    C5 --> F
    D4 --> F
    E4 --> F
    
    F --> G[Extract Matches]
    G --> H[Group by Pattern Type]
    H --> I[JSON Output with Labels]
    
    style C fill:#e8f5e8
    style D fill:#e3f2fd
    style E fill:#fff3e0
    style F fill:#f3e5f5
```

### Complex Schema Structure Visualization

```mermaid
graph TB
    subgraph "E-commerce Schema Example"
        A[Category baseSelector] --> B[Category Fields]
        A --> C[Products nested_list]
        
        B --> B1[category_name]
        B --> B2[category_id attribute]
        B --> B3[category_url attribute]
        
        C --> C1[Product baseSelector]
        C1 --> C2[name text]
        C1 --> C3[price text]
        C1 --> C4[Details nested object]
        C1 --> C5[Features list]
        C1 --> C6[Reviews nested_list]
        
        C4 --> C4a[brand text]
        C4 --> C4b[model text]
        C4 --> C4c[specs html]
        
        C5 --> C5a[feature text array]
        
        C6 --> C6a[reviewer text]
        C6 --> C6b[rating attribute]
        C6 --> C6c[comment text]
        C6 --> C6d[date attribute]
    end
    
    subgraph "JSON Output Structure"
        D[categories array] --> D1[category object]
        D1 --> D2[category_name]
        D1 --> D3[category_id]
        D1 --> D4[products array]
        
        D4 --> D5[product object]
        D5 --> D6[name, price]
        D5 --> D7[details object]
        D5 --> D8[features array]
        D5 --> D9[reviews array]
        
        D7 --> D7a[brand, model, specs]
        D8 --> D8a[feature strings]
        D9 --> D9a[review objects]
    end
    
    A -.-> D
    B1 -.-> D2
    C2 -.-> D6
    C4 -.-> D7
    C5 -.-> D8
    C6 -.-> D9
    
    style A fill:#e3f2fd
    style C fill:#f3e5f5
    style C4 fill:#e8f5e8
    style D fill:#fff3e0
```

### Error Handling and Fallback Strategy

```mermaid
stateDiagram-v2
    [*] --> PrimaryStrategy
    
    PrimaryStrategy --> Success: Extraction successful
    PrimaryStrategy --> ValidationFailed: Invalid data
    PrimaryStrategy --> ExtractionFailed: No matches found
    PrimaryStrategy --> TimeoutError: LLM timeout
    
    ValidationFailed --> FallbackStrategy: Try alternative
    ExtractionFailed --> FallbackStrategy: Try alternative
    TimeoutError --> FallbackStrategy: Try alternative
    
    FallbackStrategy --> FallbackSuccess: Fallback works
    FallbackStrategy --> FallbackFailed: All strategies failed
    
    FallbackSuccess --> Success: Return results
    FallbackFailed --> ErrorReport: Log failure details
    
    Success --> [*]: Complete
    ErrorReport --> [*]: Return empty results
    
    note right of PrimaryStrategy : Try fastest/most accurate first
    note right of FallbackStrategy : Use simpler but reliable method
    note left of ErrorReport : Provide debugging information
```

### Token Usage and Cost Optimization

```mermaid
flowchart TD
    A[LLM Extraction Request] --> B{Content Size Check}
    
    B -->|Small < 1200 tokens| C[Single LLM Call]
    B -->|Large > 1200 tokens| D[Chunking Strategy]
    
    C --> C1[Send full content]
    C1 --> C2[Parse JSON response]
    C2 --> C3[Track token usage]
    
    D --> D1[Split into chunks]
    D1 --> D2[Add overlap between chunks]
    D2 --> D3[Process chunks in parallel]
    
    D3 --> D4[Chunk 1 → LLM]
    D3 --> D5[Chunk 2 → LLM]
    D3 --> D6[Chunk N → LLM]
    
    D4 --> D7[Merge results]
    D5 --> D7
    D6 --> D7
    
    D7 --> D8[Deduplicate data]
    D8 --> D9[Aggregate token usage]
    
    C3 --> E[Cost Calculation]
    D9 --> E
    
    E --> F[Usage Report]
    F --> F1[Prompt tokens: X]
    F --> F2[Completion tokens: Y]
    F --> F3[Total cost: $Z]
    
    style C fill:#c8e6c9
    style D fill:#fff3e0
    style E fill:#e3f2fd
    style F fill:#f3e5f5
```

**📖 Learn more:** [LLM Strategies](https://docs.crawl4ai.com/extraction/llm-strategies/), [Schema-Based Extraction](https://docs.crawl4ai.com/extraction/no-llm-strategies/), [Pattern Matching](https://docs.crawl4ai.com/extraction/no-llm-strategies/#regexextractionstrategy), [Performance Optimization](https://docs.crawl4ai.com/advanced/multi-url-crawling/)

---


## Docker - Full Content
Component ID: docker
Context Type: memory
Estimated tokens: 5,155

## Docker Deployment

Complete Docker deployment guide with pre-built images, API endpoints, configuration, and MCP integration.

### Quick Start with Pre-built Images

```bash
# Pull latest image
docker pull unclecode/crawl4ai:latest

# Setup LLM API keys
cat > .llm.env << EOL
OPENAI_API_KEY=sk-your-key
ANTHROPIC_API_KEY=your-anthropic-key
GROQ_API_KEY=your-groq-key
GEMINI_API_TOKEN=your-gemini-token
EOL

# Run with LLM support
docker run -d \
  -p 11235:11235 \
  --name crawl4ai \
  --env-file .llm.env \
  --shm-size=1g \
  unclecode/crawl4ai:latest

# Basic run (no LLM)
docker run -d \
  -p 11235:11235 \
  --name crawl4ai \
  --shm-size=1g \
  unclecode/crawl4ai:latest

# Check health
curl http://localhost:11235/health
```

### Docker Compose Deployment

```bash
# Clone and setup
git clone https://github.com/unclecode/crawl4ai.git
cd crawl4ai
cp deploy/docker/.llm.env.example .llm.env
# Edit .llm.env with your API keys

# Run pre-built image
IMAGE=unclecode/crawl4ai:latest docker compose up -d

# Build locally
docker compose up --build -d

# Build with all features
INSTALL_TYPE=all docker compose up --build -d

# Build with GPU support
ENABLE_GPU=true docker compose up --build -d

# Stop service
docker compose down
```

### Manual Build with Multi-Architecture

```bash
# Clone repository
git clone https://github.com/unclecode/crawl4ai.git
cd crawl4ai

# Build for current architecture
docker buildx build -t crawl4ai-local:latest --load .

# Build for multiple architectures
docker buildx build --platform linux/amd64,linux/arm64 \
  -t crawl4ai-local:latest --load .

# Build with specific features
docker buildx build \
  --build-arg INSTALL_TYPE=all \
  --build-arg ENABLE_GPU=false \
  -t crawl4ai-local:latest --load .

# Run custom build
docker run -d \
  -p 11235:11235 \
  --name crawl4ai-custom \
  --env-file .llm.env \
  --shm-size=1g \
  crawl4ai-local:latest
```

### Build Arguments

```bash
# Available build options
docker buildx build \
  --build-arg INSTALL_TYPE=all \     # default|all|torch|transformer
  --build-arg ENABLE_GPU=true \      # true|false
  --build-arg APP_HOME=/app \        # Install path
  --build-arg USE_LOCAL=true \       # Use local source
  --build-arg GITHUB_REPO=url \      # Git repo if USE_LOCAL=false
  --build-arg GITHUB_BRANCH=main \   # Git branch
  -t crawl4ai-custom:latest --load .
```

### Core API Endpoints

```python
# Main crawling endpoints
import requests
import json

# Basic crawl
payload = {
    "urls": ["https://example.com"],
    "browser_config": {"type": "BrowserConfig", "params": {"headless": True}},
    "crawler_config": {"type": "CrawlerRunConfig", "params": {"cache_mode": "bypass"}}
}
response = requests.post("http://localhost:11235/crawl", json=payload)

# Streaming crawl
payload["crawler_config"]["params"]["stream"] = True
response = requests.post("http://localhost:11235/crawl/stream", json=payload)

# Health check
response = requests.get("http://localhost:11235/health")

# API schema
response = requests.get("http://localhost:11235/schema")

# Metrics (Prometheus format)
response = requests.get("http://localhost:11235/metrics")
```

### Specialized Endpoints

```python
# HTML extraction (preprocessed for schema)
response = requests.post("http://localhost:11235/html", 
    json={"url": "https://example.com"})

# Screenshot capture
response = requests.post("http://localhost:11235/screenshot", json={
    "url": "https://example.com",
    "screenshot_wait_for": 2,
    "output_path": "/path/to/save/screenshot.png"
})

# PDF generation
response = requests.post("http://localhost:11235/pdf", json={
    "url": "https://example.com",
    "output_path": "/path/to/save/document.pdf"
})

# JavaScript execution
response = requests.post("http://localhost:11235/execute_js", json={
    "url": "https://example.com",
    "scripts": [
        "return document.title",
        "return Array.from(document.querySelectorAll('a')).map(a => a.href)"
    ]
})

# Markdown generation
response = requests.post("http://localhost:11235/md", json={
    "url": "https://example.com",
    "f": "fit",  # raw|fit|bm25|llm
    "q": "extract main content",  # query for filtering
    "c": "0"  # cache: 0=bypass, 1=use
})

# LLM Q&A
response = requests.get("http://localhost:11235/llm/https://example.com?q=What is this page about?")

# Library context (for AI assistants)
response = requests.get("http://localhost:11235/ask", params={
    "context_type": "all",  # code|doc|all
    "query": "how to use extraction strategies",
    "score_ratio": 0.5,
    "max_results": 20
})
```

### Python SDK Usage

```python
import asyncio
from crawl4ai.docker_client import Crawl4aiDockerClient
from crawl4ai import BrowserConfig, CrawlerRunConfig, CacheMode

async def main():
    async with Crawl4aiDockerClient(base_url="http://localhost:11235") as client:
        # Non-streaming crawl
        results = await client.crawl(
            ["https://example.com"],
            browser_config=BrowserConfig(headless=True),
            crawler_config=CrawlerRunConfig(cache_mode=CacheMode.BYPASS)
        )
        
        for result in results:
            print(f"URL: {result.url}, Success: {result.success}")
            print(f"Content length: {len(result.markdown)}")
        
        # Streaming crawl
        stream_config = CrawlerRunConfig(stream=True, cache_mode=CacheMode.BYPASS)
        async for result in await client.crawl(
            ["https://example.com", "https://python.org"],
            browser_config=BrowserConfig(headless=True),
            crawler_config=stream_config
        ):
            print(f"Streamed: {result.url} - {result.success}")
        
        # Get API schema
        schema = await client.get_schema()
        print(f"Schema available: {bool(schema)}")

asyncio.run(main())
```

### Advanced API Configuration

```python
# Complex extraction with LLM
payload = {
    "urls": ["https://example.com"],
    "browser_config": {
        "type": "BrowserConfig",
        "params": {
            "headless": True,
            "viewport": {"type": "dict", "value": {"width": 1200, "height": 800}}
        }
    },
    "crawler_config": {
        "type": "CrawlerRunConfig",
        "params": {
            "extraction_strategy": {
                "type": "LLMExtractionStrategy",
                "params": {
                    "llm_config": {
                        "type": "LLMConfig",
                        "params": {
                            "provider": "openai/gpt-4o-mini",
                            "api_token": "env:OPENAI_API_KEY"
                        }
                    },
                    "schema": {
                        "type": "dict",
                        "value": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "content": {"type": "string"}
                            }
                        }
                    },
                    "instruction": "Extract title and main content"
                }
            },
            "markdown_generator": {
                "type": "DefaultMarkdownGenerator",
                "params": {
                    "content_filter": {
                        "type": "PruningContentFilter",
                        "params": {"threshold": 0.6}
                    }
                }
            }
        }
    }
}

response = requests.post("http://localhost:11235/crawl", json=payload)
```

### CSS Extraction Strategy

```python
# CSS-based structured extraction
schema = {
    "name": "ProductList",
    "baseSelector": ".product",
    "fields": [
        {"name": "title", "selector": "h2", "type": "text"},
        {"name": "price", "selector": ".price", "type": "text"},
        {"name": "link", "selector": "a", "type": "attribute", "attribute": "href"}
    ]
}

payload = {
    "urls": ["https://example-shop.com"],
    "browser_config": {"type": "BrowserConfig", "params": {"headless": True}},
    "crawler_config": {
        "type": "CrawlerRunConfig",
        "params": {
            "extraction_strategy": {
                "type": "JsonCssExtractionStrategy",
                "params": {
                    "schema": {"type": "dict", "value": schema}
                }
            }
        }
    }
}

response = requests.post("http://localhost:11235/crawl", json=payload)
data = response.json()
extracted = json.loads(data["results"][0]["extracted_content"])
```

### MCP (Model Context Protocol) Integration

```bash
# Add Crawl4AI as MCP provider to Claude Code
claude mcp add --transport sse c4ai-sse http://localhost:11235/mcp/sse

# List MCP providers
claude mcp list

# Test MCP connection
python tests/mcp/test_mcp_socket.py

# Available MCP endpoints
# SSE: http://localhost:11235/mcp/sse
# WebSocket: ws://localhost:11235/mcp/ws
# Schema: http://localhost:11235/mcp/schema
```

Available MCP tools:
- `md` - Generate markdown from web content
- `html` - Extract preprocessed HTML  
- `screenshot` - Capture webpage screenshots
- `pdf` - Generate PDF documents
- `execute_js` - Run JavaScript on web pages
- `crawl` - Perform multi-URL crawling
- `ask` - Query Crawl4AI library context

### Configuration Management

```yaml
# config.yml structure
app:
  title: "Crawl4AI API"
  version: "1.0.0"
  host: "0.0.0.0"
  port: 11235
  timeout_keep_alive: 300

llm:
  provider: "openai/gpt-4o-mini"
  api_key_env: "OPENAI_API_KEY"

security:
  enabled: false
  jwt_enabled: false
  trusted_hosts: ["*"]

crawler:
  memory_threshold_percent: 95.0
  rate_limiter:
    base_delay: [1.0, 2.0]
  timeouts:
    stream_init: 30.0
    batch_process: 300.0
  pool:
    max_pages: 40
    idle_ttl_sec: 1800

rate_limiting:
  enabled: true
  default_limit: "1000/minute"
  storage_uri: "memory://"

logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

### Custom Configuration Deployment

```bash
# Method 1: Mount custom config
docker run -d -p 11235:11235 \
  --name crawl4ai-custom \
  --env-file .llm.env \
  --shm-size=1g \
  -v $(pwd)/my-config.yml:/app/config.yml \
  unclecode/crawl4ai:latest

# Method 2: Build with custom config
# Edit deploy/docker/config.yml then build
docker buildx build -t crawl4ai-custom:latest --load .
```

### Monitoring and Health Checks

```bash
# Health endpoint
curl http://localhost:11235/health

# Prometheus metrics
curl http://localhost:11235/metrics

# Configuration validation
curl -X POST http://localhost:11235/config/dump \
  -H "Content-Type: application/json" \
  -d '{"code": "CrawlerRunConfig(cache_mode=\"BYPASS\", screenshot=True)"}'
```

### Playground Interface

Access the interactive playground at `http://localhost:11235/playground` for:
- Testing configurations with visual interface
- Generating JSON payloads for REST API
- Converting Python config to JSON format
- Testing crawl operations directly in browser

### Async Job Processing

```python
# Submit job for async processing
import time

# Submit crawl job
response = requests.post("http://localhost:11235/crawl/job", json=payload)
task_id = response.json()["task_id"]

# Poll for completion
while True:
    result = requests.get(f"http://localhost:11235/crawl/job/{task_id}")
    status = result.json()
    
    if status["status"] in ["COMPLETED", "FAILED"]:
        break
    time.sleep(1.5)

print("Final result:", status)
```

### Production Deployment

```bash
# Production-ready deployment
docker run -d \
  --name crawl4ai-prod \
  --restart unless-stopped \
  -p 11235:11235 \
  --env-file .llm.env \
  --shm-size=2g \
  --memory=8g \
  --cpus=4 \
  -v /path/to/custom-config.yml:/app/config.yml \
  unclecode/crawl4ai:latest

# With Docker Compose for production
version: '3.8'
services:
  crawl4ai:
    image: unclecode/crawl4ai:latest
    ports:
      - "11235:11235"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    volumes:
      - ./config.yml:/app/config.yml
    shm_size: 2g
    deploy:
      resources:
        limits:
          memory: 8G
          cpus: '4'
    restart: unless-stopped
```

### Configuration Validation and JSON Structure

```python
# Method 1: Create config objects and dump to see expected JSON structure
from crawl4ai import BrowserConfig, CrawlerRunConfig, LLMConfig, CacheMode
from crawl4ai import JsonCssExtractionStrategy, LLMExtractionStrategy
import json

# Create browser config and see JSON structure
browser_config = BrowserConfig(
    headless=True,
    viewport_width=1280,
    viewport_height=720,
    proxy="http://user:pass@proxy:8080"
)

# Get JSON structure
browser_json = browser_config.dump()
print("BrowserConfig JSON structure:")
print(json.dumps(browser_json, indent=2))

# Create crawler config with extraction strategy
schema = {
    "name": "Articles",
    "baseSelector": ".article",
    "fields": [
        {"name": "title", "selector": "h2", "type": "text"},
        {"name": "content", "selector": ".content", "type": "html"}
    ]
}

crawler_config = CrawlerRunConfig(
    cache_mode=CacheMode.BYPASS,
    screenshot=True,
    extraction_strategy=JsonCssExtractionStrategy(schema),
    js_code=["window.scrollTo(0, document.body.scrollHeight);"],
    wait_for="css:.loaded"
)

crawler_json = crawler_config.dump()
print("\nCrawlerRunConfig JSON structure:")
print(json.dumps(crawler_json, indent=2))
```

### Reverse Validation - JSON to Objects

```python
# Method 2: Load JSON back to config objects for validation
from crawl4ai.async_configs import from_serializable_dict

# Test JSON structure by converting back to objects
test_browser_json = {
    "type": "BrowserConfig",
    "params": {
        "headless": True,
        "viewport_width": 1280,
        "proxy": "http://user:pass@proxy:8080"
    }
}

try:
    # Convert JSON back to object
    restored_browser = from_serializable_dict(test_browser_json)
    print(f"✅ Valid BrowserConfig: {type(restored_browser)}")
    print(f"Headless: {restored_browser.headless}")
    print(f"Proxy: {restored_browser.proxy}")
except Exception as e:
    print(f"❌ Invalid BrowserConfig JSON: {e}")

# Test complex crawler config JSON
test_crawler_json = {
    "type": "CrawlerRunConfig", 
    "params": {
        "cache_mode": "bypass",
        "screenshot": True,
        "extraction_strategy": {
            "type": "JsonCssExtractionStrategy",
            "params": {
                "schema": {
                    "type": "dict",
                    "value": {
                        "name": "Products",
                        "baseSelector": ".product",
                        "fields": [
                            {"name": "title", "selector": "h3", "type": "text"}
                        ]
                    }
                }
            }
        }
    }
}

try:
    restored_crawler = from_serializable_dict(test_crawler_json)
    print(f"✅ Valid CrawlerRunConfig: {type(restored_crawler)}")
    print(f"Cache mode: {restored_crawler.cache_mode}")
    print(f"Has extraction strategy: {restored_crawler.extraction_strategy is not None}")
except Exception as e:
    print(f"❌ Invalid CrawlerRunConfig JSON: {e}")
```

### Using Server's /config/dump Endpoint for Validation

```python
import requests

# Method 3: Use server endpoint to validate configuration syntax
def validate_config_with_server(config_code: str) -> dict:
    """Validate configuration using server's /config/dump endpoint"""
    response = requests.post(
        "http://localhost:11235/config/dump",
        json={"code": config_code}
    )
    
    if response.status_code == 200:
        print("✅ Valid configuration syntax")
        return response.json()
    else:
        print(f"❌ Invalid configuration: {response.status_code}")
        print(response.json())
        return None

# Test valid configuration
valid_config = """
CrawlerRunConfig(
    cache_mode=CacheMode.BYPASS,
    screenshot=True,
    js_code=["window.scrollTo(0, document.body.scrollHeight);"],
    wait_for="css:.content-loaded"
)
"""

result = validate_config_with_server(valid_config)
if result:
    print("Generated JSON structure:")
    print(json.dumps(result, indent=2))

# Test invalid configuration (should fail)
invalid_config = """
CrawlerRunConfig(
    cache_mode="invalid_mode",
    screenshot=True,
    js_code=some_function()  # This will fail
)
"""

validate_config_with_server(invalid_config)
```

### Configuration Builder Helper

```python
def build_and_validate_request(urls, browser_params=None, crawler_params=None):
    """Helper to build and validate complete request payload"""
    
    # Create configurations
    browser_config = BrowserConfig(**(browser_params or {}))
    crawler_config = CrawlerRunConfig(**(crawler_params or {}))
    
    # Build complete request payload
    payload = {
        "urls": urls if isinstance(urls, list) else [urls],
        "browser_config": browser_config.dump(),
        "crawler_config": crawler_config.dump()
    }
    
    print("✅ Complete request payload:")
    print(json.dumps(payload, indent=2))
    
    # Validate by attempting to reconstruct
    try:
        test_browser = from_serializable_dict(payload["browser_config"])
        test_crawler = from_serializable_dict(payload["crawler_config"])
        print("✅ Payload validation successful")
        return payload
    except Exception as e:
        print(f"❌ Payload validation failed: {e}")
        return None

# Example usage
payload = build_and_validate_request(
    urls=["https://example.com"],
    browser_params={"headless": True, "viewport_width": 1280},
    crawler_params={
        "cache_mode": CacheMode.BYPASS,
        "screenshot": True,
        "word_count_threshold": 10
    }
)

if payload:
    # Send to server
    response = requests.post("http://localhost:11235/crawl", json=payload)
    print(f"Server response: {response.status_code}")
```

### Common JSON Structure Patterns

```python
# Pattern 1: Simple primitive values
simple_config = {
    "type": "CrawlerRunConfig",
    "params": {
        "cache_mode": "bypass",  # String enum value
        "screenshot": True,      # Boolean
        "page_timeout": 60000   # Integer
    }
}

# Pattern 2: Nested objects
nested_config = {
    "type": "CrawlerRunConfig", 
    "params": {
        "extraction_strategy": {
            "type": "LLMExtractionStrategy",
            "params": {
                "llm_config": {
                    "type": "LLMConfig",
                    "params": {
                        "provider": "openai/gpt-4o-mini",
                        "api_token": "env:OPENAI_API_KEY"
                    }
                },
                "instruction": "Extract main content"
            }
        }
    }
}

# Pattern 3: Dictionary values (must use type: dict wrapper)
dict_config = {
    "type": "CrawlerRunConfig",
    "params": {
        "extraction_strategy": {
            "type": "JsonCssExtractionStrategy", 
            "params": {
                "schema": {
                    "type": "dict",  # Required wrapper
                    "value": {       # Actual dictionary content
                        "name": "Products",
                        "baseSelector": ".product",
                        "fields": [
                            {"name": "title", "selector": "h2", "type": "text"}
                        ]
                    }
                }
            }
        }
    }
}

# Pattern 4: Lists and arrays
list_config = {
    "type": "CrawlerRunConfig",
    "params": {
        "js_code": [  # Lists are handled directly
            "window.scrollTo(0, document.body.scrollHeight);",
            "document.querySelector('.load-more')?.click();"
        ],
        "excluded_tags": ["script", "style", "nav"]
    }
}
```

### Troubleshooting Common JSON Errors

```python
def diagnose_json_errors():
    """Common JSON structure errors and fixes"""
    
    # ❌ WRONG: Missing type wrapper for objects
    wrong_config = {
        "browser_config": {
            "headless": True  # Missing type wrapper
        }
    }
    
    # ✅ CORRECT: Proper type wrapper
    correct_config = {
        "browser_config": {
            "type": "BrowserConfig",
            "params": {
                "headless": True
            }
        }
    }
    
    # ❌ WRONG: Dictionary without type: dict wrapper  
    wrong_dict = {
        "schema": {
            "name": "Products"  # Raw dict, should be wrapped
        }
    }
    
    # ✅ CORRECT: Dictionary with proper wrapper
    correct_dict = {
        "schema": {
            "type": "dict",
            "value": {
                "name": "Products"
            }
        }
    }
    
    # ❌ WRONG: Invalid enum string
    wrong_enum = {
        "cache_mode": "DISABLED"  # Wrong case/value
    }
    
    # ✅ CORRECT: Valid enum string  
    correct_enum = {
        "cache_mode": "bypass"  # or "enabled", "disabled", etc.
    }
    
    print("Common error patterns documented above")

# Validate your JSON structure before sending
def pre_flight_check(payload):
    """Run checks before sending to server"""
    required_keys = ["urls", "browser_config", "crawler_config"]
    
    for key in required_keys:
        if key not in payload:
            print(f"❌ Missing required key: {key}")
            return False
    
    # Check type wrappers
    for config_key in ["browser_config", "crawler_config"]:
        config = payload[config_key]
        if not isinstance(config, dict) or "type" not in config:
            print(f"❌ {config_key} missing type wrapper")
            return False
        if "params" not in config:
            print(f"❌ {config_key} missing params")
            return False
    
    print("✅ Pre-flight check passed")
    return True

# Example usage
payload = {
    "urls": ["https://example.com"],
    "browser_config": {"type": "BrowserConfig", "params": {"headless": True}},
    "crawler_config": {"type": "CrawlerRunConfig", "params": {"cache_mode": "bypass"}}
}

if pre_flight_check(payload):
    # Safe to send to server
    pass
```

**📖 Learn more:** [Complete Docker Guide](https://docs.crawl4ai.com/core/docker-deployment/), [API Reference](https://docs.crawl4ai.com/api/), [MCP Integration](https://docs.crawl4ai.com/core/docker-deployment/#mcp-model-context-protocol-support), [Configuration Options](https://docs.crawl4ai.com/core/docker-deployment/#server-configuration)

---


## Docker - Diagrams & Workflows
Component ID: docker
Context Type: reasoning
Estimated tokens: 4,308

## Docker Deployment Architecture and Workflows

Visual representations of Crawl4AI Docker deployment, API architecture, configuration management, and service interactions.

### Docker Deployment Decision Flow

```mermaid
flowchart TD
    A[Start Docker Deployment] --> B{Deployment Type?}
    
    B -->|Quick Start| C[Pre-built Image]
    B -->|Development| D[Docker Compose]
    B -->|Custom Build| E[Manual Build]
    B -->|Production| F[Production Setup]
    
    C --> C1[docker pull unclecode/crawl4ai]
    C1 --> C2{Need LLM Support?}
    C2 -->|Yes| C3[Setup .llm.env]
    C2 -->|No| C4[Basic run]
    C3 --> C5[docker run with --env-file]
    C4 --> C6[docker run basic]
    
    D --> D1[git clone repository]
    D1 --> D2[cp .llm.env.example .llm.env]
    D2 --> D3{Build Type?}
    D3 -->|Pre-built| D4[IMAGE=latest docker compose up]
    D3 -->|Local Build| D5[docker compose up --build]
    D3 -->|All Features| D6[INSTALL_TYPE=all docker compose up]
    
    E --> E1[docker buildx build]
    E1 --> E2{Architecture?}
    E2 -->|Single| E3[--platform linux/amd64]
    E2 -->|Multi| E4[--platform linux/amd64,linux/arm64]
    E3 --> E5[Build complete]
    E4 --> E5
    
    F --> F1[Production configuration]
    F1 --> F2[Custom config.yml]
    F2 --> F3[Resource limits]
    F3 --> F4[Health monitoring]
    F4 --> F5[Production ready]
    
    C5 --> G[Service running on :11235]
    C6 --> G
    D4 --> G
    D5 --> G
    D6 --> G
    E5 --> H[docker run custom image]
    H --> G
    F5 --> I[Production deployment]
    
    G --> J[Access playground at /playground]
    G --> K[Health check at /health]
    I --> L[Production monitoring]
    
    style A fill:#e1f5fe
    style G fill:#c8e6c9
    style I fill:#c8e6c9
    style J fill:#fff3e0
    style K fill:#fff3e0
    style L fill:#e8f5e8
```

### Docker Container Architecture

```mermaid
graph TB
    subgraph "Host Environment"
        A[Docker Engine] --> B[Crawl4AI Container]
        C[.llm.env] --> B
        D[Custom config.yml] --> B
        E[Port 11235] --> B
        F[Shared Memory 1GB+] --> B
    end
    
    subgraph "Container Services"
        B --> G[FastAPI Server :8020]
        B --> H[Gunicorn WSGI]
        B --> I[Supervisord Process Manager]
        B --> J[Redis Cache :6379]
        
        G --> K[REST API Endpoints]
        G --> L[WebSocket Connections]
        G --> M[MCP Protocol]
        
        H --> N[Worker Processes]
        I --> O[Service Monitoring]
        J --> P[Request Caching]
    end
    
    subgraph "Browser Management"
        B --> Q[Playwright Framework]
        Q --> R[Chromium Browser]
        Q --> S[Firefox Browser]
        Q --> T[WebKit Browser]
        
        R --> U[Browser Pool]
        S --> U
        T --> U
        
        U --> V[Page Sessions]
        U --> W[Context Management]
    end
    
    subgraph "External Services"
        X[OpenAI API] -.-> K
        Y[Anthropic Claude] -.-> K
        Z[Local Ollama] -.-> K
        AA[Groq API] -.-> K
        BB[Google Gemini] -.-> K
    end
    
    subgraph "Client Interactions"
        CC[Python SDK] --> K
        DD[REST API Calls] --> K
        EE[MCP Clients] --> M
        FF[Web Browser] --> G
        GG[Monitoring Tools] --> K
    end
    
    style B fill:#e3f2fd
    style G fill:#f3e5f5
    style Q fill:#e8f5e8
    style K fill:#fff3e0
```

### API Endpoints Architecture

```mermaid
graph LR
    subgraph "Core Endpoints"
        A[/crawl] --> A1[Single URL crawl]
        A2[/crawl/stream] --> A3[Streaming multi-URL]
        A4[/crawl/job] --> A5[Async job submission]
        A6[/crawl/job/{id}] --> A7[Job status check]
    end
    
    subgraph "Specialized Endpoints"
        B[/html] --> B1[Preprocessed HTML]
        B2[/screenshot] --> B3[PNG capture]
        B4[/pdf] --> B5[PDF generation]
        B6[/execute_js] --> B7[JavaScript execution]
        B8[/md] --> B9[Markdown extraction]
    end
    
    subgraph "Utility Endpoints"
        C[/health] --> C1[Service status]
        C2[/metrics] --> C3[Prometheus metrics]
        C4[/schema] --> C5[API documentation]
        C6[/playground] --> C7[Interactive testing]
    end
    
    subgraph "LLM Integration"
        D[/llm/{url}] --> D1[Q&A over URL]
        D2[/ask] --> D3[Library context search]
        D4[/config/dump] --> D5[Config validation]
    end
    
    subgraph "MCP Protocol"
        E[/mcp/sse] --> E1[Server-Sent Events]
        E2[/mcp/ws] --> E3[WebSocket connection]
        E4[/mcp/schema] --> E5[MCP tool definitions]
    end
    
    style A fill:#e3f2fd
    style B fill:#f3e5f5
    style C fill:#e8f5e8
    style D fill:#fff3e0
    style E fill:#fce4ec
```

### Request Processing Flow

```mermaid
sequenceDiagram
    participant Client
    participant FastAPI
    participant RequestValidator
    participant BrowserPool
    participant Playwright
    participant ExtractionEngine
    participant LLMProvider
    
    Client->>FastAPI: POST /crawl with config
    FastAPI->>RequestValidator: Validate JSON structure
    
    alt Valid Request
        RequestValidator-->>FastAPI: ✓ Validated
        FastAPI->>BrowserPool: Request browser instance
        BrowserPool->>Playwright: Launch browser/reuse session
        Playwright-->>BrowserPool: Browser ready
        BrowserPool-->>FastAPI: Browser allocated
        
        FastAPI->>Playwright: Navigate to URL
        Playwright->>Playwright: Execute JS, wait conditions
        Playwright-->>FastAPI: Page content ready
        
        FastAPI->>ExtractionEngine: Process content
        
        alt LLM Extraction
            ExtractionEngine->>LLMProvider: Send content + schema
            LLMProvider-->>ExtractionEngine: Structured data
        else CSS Extraction
            ExtractionEngine->>ExtractionEngine: Apply CSS selectors
        end
        
        ExtractionEngine-->>FastAPI: Extraction complete
        FastAPI->>BrowserPool: Release browser
        FastAPI-->>Client: CrawlResult response
        
    else Invalid Request
        RequestValidator-->>FastAPI: ✗ Validation error
        FastAPI-->>Client: 400 Bad Request
    end
```

### Configuration Management Flow

```mermaid
stateDiagram-v2
    [*] --> ConfigLoading
    
    ConfigLoading --> DefaultConfig: Load default config.yml
    ConfigLoading --> CustomConfig: Custom config mounted
    ConfigLoading --> EnvOverrides: Environment variables
    
    DefaultConfig --> ConfigMerging
    CustomConfig --> ConfigMerging
    EnvOverrides --> ConfigMerging
    
    ConfigMerging --> ConfigValidation
    
    ConfigValidation --> Valid: Schema validation passes
    ConfigValidation --> Invalid: Validation errors
    
    Invalid --> ConfigError: Log errors and exit
    ConfigError --> [*]
    
    Valid --> ServiceInitialization
    ServiceInitialization --> FastAPISetup
    ServiceInitialization --> BrowserPoolInit
    ServiceInitialization --> CacheSetup
    
    FastAPISetup --> Running
    BrowserPoolInit --> Running
    CacheSetup --> Running
    
    Running --> ConfigReload: Config change detected
    ConfigReload --> ConfigValidation
    
    Running --> [*]: Service shutdown
    
    note right of ConfigMerging : Priority: ENV > Custom > Default
    note right of ServiceInitialization : All services must initialize successfully
```

### Multi-Architecture Build Process

```mermaid
flowchart TD
    A[Developer Push] --> B[GitHub Repository]
    
    B --> C[Docker Buildx]
    C --> D{Build Strategy}
    
    D -->|Multi-arch| E[Parallel Builds]
    D -->|Single-arch| F[Platform-specific Build]
    
    E --> G[AMD64 Build]
    E --> H[ARM64 Build]
    
    F --> I[Target Platform Build]
    
    subgraph "AMD64 Build Process"
        G --> G1[Ubuntu base image]
        G1 --> G2[Python 3.11 install]
        G2 --> G3[System dependencies]
        G3 --> G4[Crawl4AI installation]
        G4 --> G5[Playwright setup]
        G5 --> G6[FastAPI configuration]
        G6 --> G7[AMD64 image ready]
    end
    
    subgraph "ARM64 Build Process"
        H --> H1[Ubuntu ARM64 base]
        H1 --> H2[Python 3.11 install]
        H2 --> H3[ARM-specific deps]
        H3 --> H4[Crawl4AI installation]
        H4 --> H5[Playwright setup]
        H5 --> H6[FastAPI configuration]
        H6 --> H7[ARM64 image ready]
    end
    
    subgraph "Single Architecture"
        I --> I1[Base image selection]
        I1 --> I2[Platform dependencies]
        I2 --> I3[Application setup]
        I3 --> I4[Platform image ready]
    end
    
    G7 --> J[Multi-arch Manifest]
    H7 --> J
    I4 --> K[Platform Image]
    
    J --> L[Docker Hub Registry]
    K --> L
    
    L --> M[Pull Request Auto-selects Architecture]
    
    style A fill:#e1f5fe
    style J fill:#c8e6c9
    style K fill:#c8e6c9
    style L fill:#f3e5f5
    style M fill:#e8f5e8
```

### MCP Integration Architecture

```mermaid
graph TB
    subgraph "MCP Client Applications"
        A[Claude Code] --> B[MCP Protocol]
        C[Cursor IDE] --> B
        D[Windsurf] --> B
        E[Custom MCP Client] --> B
    end
    
    subgraph "Crawl4AI MCP Server"
        B --> F[MCP Endpoint Router]
        F --> G[SSE Transport /mcp/sse]
        F --> H[WebSocket Transport /mcp/ws]
        F --> I[Schema Endpoint /mcp/schema]
        
        G --> J[MCP Tool Handler]
        H --> J
        
        J --> K[Tool: md]
        J --> L[Tool: html]
        J --> M[Tool: screenshot]
        J --> N[Tool: pdf]
        J --> O[Tool: execute_js]
        J --> P[Tool: crawl]
        J --> Q[Tool: ask]
    end
    
    subgraph "Crawl4AI Core Services"
        K --> R[Markdown Generator]
        L --> S[HTML Preprocessor]
        M --> T[Screenshot Service]
        N --> U[PDF Generator]
        O --> V[JavaScript Executor]
        P --> W[Batch Crawler]
        Q --> X[Context Search]
        
        R --> Y[Browser Pool]
        S --> Y
        T --> Y
        U --> Y
        V --> Y
        W --> Y
        X --> Z[Knowledge Base]
    end
    
    subgraph "External Resources"
        Y --> AA[Playwright Browsers]
        Z --> BB[Library Documentation]
        Z --> CC[Code Examples]
        AA --> DD[Web Pages]
    end
    
    style B fill:#e3f2fd
    style J fill:#f3e5f5
    style Y fill:#e8f5e8
    style Z fill:#fff3e0
```

### API Request/Response Flow Patterns

```mermaid
sequenceDiagram
    participant Client
    participant LoadBalancer
    participant FastAPI
    participant ConfigValidator
    participant BrowserManager
    participant CrawlEngine
    participant ResponseBuilder
    
    Note over Client,ResponseBuilder: Basic Crawl Request
    
    Client->>LoadBalancer: POST /crawl
    LoadBalancer->>FastAPI: Route request
    
    FastAPI->>ConfigValidator: Validate browser_config
    ConfigValidator-->>FastAPI: ✓ Valid BrowserConfig
    
    FastAPI->>ConfigValidator: Validate crawler_config
    ConfigValidator-->>FastAPI: ✓ Valid CrawlerRunConfig
    
    FastAPI->>BrowserManager: Allocate browser
    BrowserManager-->>FastAPI: Browser instance
    
    FastAPI->>CrawlEngine: Execute crawl
    
    Note over CrawlEngine: Page processing
    CrawlEngine->>CrawlEngine: Navigate & wait
    CrawlEngine->>CrawlEngine: Extract content
    CrawlEngine->>CrawlEngine: Apply strategies
    
    CrawlEngine-->>FastAPI: CrawlResult
    
    FastAPI->>ResponseBuilder: Format response
    ResponseBuilder-->>FastAPI: JSON response
    
    FastAPI->>BrowserManager: Release browser
    FastAPI-->>LoadBalancer: Response ready
    LoadBalancer-->>Client: 200 OK + CrawlResult
    
    Note over Client,ResponseBuilder: Streaming Request
    
    Client->>FastAPI: POST /crawl/stream
    FastAPI-->>Client: 200 OK (stream start)
    
    loop For each URL
        FastAPI->>CrawlEngine: Process URL
        CrawlEngine-->>FastAPI: Result ready
        FastAPI-->>Client: NDJSON line
    end
    
    FastAPI-->>Client: Stream completed
```

### Configuration Validation Workflow

```mermaid
flowchart TD
    A[Client Request] --> B[JSON Payload]
    B --> C{Pre-validation}
    
    C -->|✓ Valid JSON| D[Extract Configurations]
    C -->|✗ Invalid JSON| E[Return 400 Bad Request]
    
    D --> F[BrowserConfig Validation]
    D --> G[CrawlerRunConfig Validation]
    
    F --> H{BrowserConfig Valid?}
    G --> I{CrawlerRunConfig Valid?}
    
    H -->|✓ Valid| J[Browser Setup]
    H -->|✗ Invalid| K[Log Browser Config Errors]
    
    I -->|✓ Valid| L[Crawler Setup]
    I -->|✗ Invalid| M[Log Crawler Config Errors]
    
    K --> N[Collect All Errors]
    M --> N
    N --> O[Return 422 Validation Error]
    
    J --> P{Both Configs Valid?}
    L --> P
    
    P -->|✓ Yes| Q[Proceed to Crawling]
    P -->|✗ No| O
    
    Q --> R[Execute Crawl Pipeline]
    R --> S[Return CrawlResult]
    
    E --> T[Client Error Response]
    O --> T
    S --> U[Client Success Response]
    
    style A fill:#e1f5fe
    style Q fill:#c8e6c9
    style S fill:#c8e6c9
    style U fill:#c8e6c9
    style E fill:#ffcdd2
    style O fill:#ffcdd2
    style T fill:#ffcdd2
```

### Production Deployment Architecture

```mermaid
graph TB
    subgraph "Load Balancer Layer"
        A[NGINX/HAProxy] --> B[Health Check]
        A --> C[Request Routing]
        A --> D[SSL Termination]
    end
    
    subgraph "Application Layer"
        C --> E[Crawl4AI Instance 1]
        C --> F[Crawl4AI Instance 2]
        C --> G[Crawl4AI Instance N]
        
        E --> H[FastAPI Server]
        F --> I[FastAPI Server]
        G --> J[FastAPI Server]
        
        H --> K[Browser Pool 1]
        I --> L[Browser Pool 2]
        J --> M[Browser Pool N]
    end
    
    subgraph "Shared Services"
        N[Redis Cluster] --> E
        N --> F
        N --> G
        
        O[Monitoring Stack] --> P[Prometheus]
        O --> Q[Grafana]
        O --> R[AlertManager]
        
        P --> E
        P --> F
        P --> G
    end
    
    subgraph "External Dependencies"
        S[OpenAI API] -.-> H
        T[Anthropic API] -.-> I
        U[Local LLM Cluster] -.-> J
    end
    
    subgraph "Persistent Storage"
        V[Configuration Volume] --> E
        V --> F
        V --> G
        
        W[Cache Volume] --> N
        X[Logs Volume] --> O
    end
    
    style A fill:#e3f2fd
    style E fill:#f3e5f5
    style F fill:#f3e5f5
    style G fill:#f3e5f5
    style N fill:#e8f5e8
    style O fill:#fff3e0
```

### Docker Resource Management

```mermaid
graph TD
    subgraph "Resource Allocation"
        A[Host Resources] --> B[CPU Cores]
        A --> C[Memory GB]
        A --> D[Disk Space]
        A --> E[Network Bandwidth]
        
        B --> F[Container Limits]
        C --> F
        D --> F
        E --> F
    end
    
    subgraph "Container Configuration"
        F --> G[--cpus=4]
        F --> H[--memory=8g]
        F --> I[--shm-size=2g]
        F --> J[Volume Mounts]
        
        G --> K[Browser Processes]
        H --> L[Browser Memory]
        I --> M[Shared Memory for Browsers]
        J --> N[Config & Cache Storage]
    end
    
    subgraph "Monitoring & Scaling"
        O[Resource Monitor] --> P[CPU Usage %]
        O --> Q[Memory Usage %]
        O --> R[Request Queue Length]
        
        P --> S{CPU > 80%?}
        Q --> T{Memory > 90%?}
        R --> U{Queue > 100?}
        
        S -->|Yes| V[Scale Up]
        T -->|Yes| V
        U -->|Yes| V
        
        V --> W[Add Container Instance]
        W --> X[Update Load Balancer]
    end
    
    subgraph "Performance Optimization"
        Y[Browser Pool Tuning] --> Z[Max Pages: 40]
        Y --> AA[Idle TTL: 30min]
        Y --> BB[Concurrency Limits]
        
        Z --> CC[Memory Efficiency]
        AA --> DD[Resource Cleanup]
        BB --> EE[Throughput Control]
    end
    
    style A fill:#e1f5fe
    style F fill:#f3e5f5
    style O fill:#e8f5e8
    style Y fill:#fff3e0
```

**📖 Learn more:** [Docker Deployment Guide](https://docs.crawl4ai.com/core/docker-deployment/), [API Reference](https://docs.crawl4ai.com/api/), [MCP Integration](https://docs.crawl4ai.com/core/docker-deployment/#mcp-model-context-protocol-support), [Production Configuration](https://docs.crawl4ai.com/core/docker-deployment/#production-deployment)

---

