# Financial Fraud Detection Agent - Design Document

## Use Case: Real-Time Financial Fraud Detection System

### Problem Statement
Financial institutions process millions of transactions daily and need to:
- Detect fraudulent transactions in real-time
- Verify customer identity across multiple factors
- Check transactions against risk databases
- Send immediate alerts to fraud teams
- Log all investigations for compliance
- Generate fraud reports for analysis

### Solution Architecture

```
┌────────────────────────────────────────────────────────────┐
│                     Web UI (Streamlit)                      │
│  - Transaction Input                                       │
│  - Real-time Fraud Analysis                                │
│  - Alert Dashboard                                          │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ▼
┌────────────────────────────────────────────────────────────┐
│        Agent: Claude Sonnet 3.5 via Bedrock                │
│        (Intelligent decision making & orchestration)        │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       │
        ┌──────────────┴───────────────┐
        │         MCP Servers           │
        │      (6 Specialized Tools)    │
        └──────────────────────────────┘
                       │
    ┌──────────────────┼──────────────────┐
    │                  │                  │
    ▼                  ▼                  ▼
┌─────────┐      ┌──────────┐      ┌────────────┐
│  Tool 1 │      │  Tool 2  │      │   Tool 3   │
│Transaction│    │ Customer │      │  Email     │
│ Risk     │      │ Identity │      │  Alerts    │
│ Checker  │      │ Verifier │      │            │
└─────────┘      └──────────┘      └────────────┘
    │                  │                  │
    ▼                  ▼                  ▼
┌─────────┐      ┌──────────┐      ┌────────────┐
│  Tool 4 │      │  Tool 5  │      │   Tool 6   │
│ Fraud   │      │Geolocation│     │  Report    │
│ History │      │  Checker │      │ Generator  │
│ Logger  │      │          │      │            │
└─────────┘      └──────────┘      └────────────┘
```

### MCP Tools (6 Total)

#### 1. Transaction Risk Checker
**Purpose**: Analyze transaction for fraud indicators
**Parameters**:
- transaction_id: string
- customer_id: string
- amount: float
- merchant: string
- location: string
- transaction_time: string
- card_present: boolean

**Returns**: Risk score (0-100), fraud indicators, risk category

#### 2. Customer Identity Verifier
**Purpose**: Multi-factor identity verification
**Parameters**:
- customer_id: string
- device_fingerprint: string
- ip_address: string
- biometric_data: optional

**Returns**: Verification status, confidence score, matched factors

#### 3. Email Alert Sender
**Purpose**: Send real-time fraud alerts via AWS SES
**Parameters**:
- alert_type: string ("high_risk", "suspicious", "blocked")
- transaction_id: string
- customer_id: string
- risk_score: int
- details: string
- recipients: list

**Returns**: Email status, message_id

#### 4. Fraud History Logger
**Purpose**: Log all fraud investigations for compliance
**Parameters**:
- case_id: string
- transaction_data: dict
- investigation_notes: string
- agent_decision: string
- evidence: list

**Returns**: Log confirmation, case_id, timestamp

#### 5. Geolocation Risk Checker
**Purpose**: Detect impossible travel and location anomalies
**Parameters**:
- customer_id: string
- current_location: string
- previous_transaction_location: string
- time_difference_minutes: int

**Returns**: Travel feasibility, risk_score, distance_miles

#### 6. Fraud Report Generator
**Purpose**: Generate detailed fraud analysis reports
**Parameters**:
- case_id: string
- include_sections: list (["summary", "timeline", "evidence", "recommendation"])
- format: string ("pdf", "json")

**Returns**: Report URL, summary statistics

### Sample Transaction Scenarios

#### Scenario 1: High-Risk Cross-Border Transaction
```
Transaction Details:
- Customer: John Smith (C-12345)
- Amount: $4,500
- Merchant: ONLINE-STORE-RU.com
- Location: Moscow, Russia
- Time: 2:30 AM (customer's local time)
- Card Present: No
- Previous Location: New York, NY (30 minutes ago)

Expected Agent Flow:
1. check_transaction_risk → Risk Score: 95/100
2. check_geolocation_risk → Impossible travel detected
3. verify_customer_identity → Device mismatch
4. send_email_alert → High-risk alert sent
5. log_fraud_history → Case logged
6. generate_fraud_report → Report created

Agent Decision: BLOCK TRANSACTION
```

#### Scenario 2: Legitimate High-Value Purchase
```
Transaction Details:
- Customer: Sarah Johnson (C-67890)
- Amount: $3,200
- Merchant: Apple Store - Fifth Avenue
- Location: New York, NY
- Time: 2:15 PM
- Card Present: Yes
- Previous Location: New York, NY (1 hour ago)

Expected Agent Flow:
1. check_transaction_risk → Risk Score: 25/100
2. check_geolocation_risk → Normal pattern
3. verify_customer_identity → All factors match
4. log_fraud_history → Logged as reviewed
5. No alert needed

Agent Decision: APPROVE TRANSACTION
```

#### Scenario 3: Account Takeover Attempt
```
Transaction Details:
- Customer: Mike Chen (C-45678)
- Multiple rapid transactions:
  * $500 - Gas Station, LA (1:00 PM)
  * $450 - ATM, New York (1:15 PM)
  * $600 - Online purchase, London (1:30 PM)

Expected Agent Flow:
1. check_transaction_risk → Risk Score: 98/100
2. check_geolocation_risk → Multiple impossible travels
3. verify_customer_identity → Failed verification
4. send_email_alert → URGENT alert sent
5. log_fraud_history → Escalated case
6. generate_fraud_report → Comprehensive report

Agent Decision: BLOCK CARD IMMEDIATELY
```

### Web UI Features (Streamlit)

#### Main Dashboard
- **Transaction Input Form**
  - Customer ID
  - Transaction amount
  - Merchant name
  - Location
  - Additional metadata

- **Real-Time Analysis Panel**
  - Live agent reasoning display
  - Tool calls visualization
  - Risk score meter (0-100)
  - Fraud indicators list

- **Alert Feed**
  - Recent high-risk detections
  - Alert status (sent/pending)
  - Quick actions

- **Statistics Panel**
  - Transactions analyzed today
  - Fraud detected
  - Average risk score
  - Response time metrics

#### Features
- Real-time streaming responses
- Tool call visualization
- Export reports (PDF/JSON)
- Alert history
- Case management

### Technology Stack

**Backend**:
- Python 3.11+
- Strands Agent Framework
- Amazon Bedrock (Claude Sonnet 3.5)
- MCP Servers (FastMCP)
- AWS SES (Email)

**Frontend**:
- Streamlit (Web UI)
- Plotly (Charts/visualizations)
- Pandas (Data handling)

**Infrastructure**:
- Docker containers for MCP servers
- Amazon EKS for production deployment
- FSx Lustre for model storage
- CloudWatch for monitoring

### Implementation Plan

1. **Phase 1**: Create 6 MCP Servers
   - Implement each tool as separate MCP server
   - Test individual functionality
   - Deploy in Docker containers

2. **Phase 2**: Update Agent
   - Connect to all 6 MCP servers
   - Configure Claude Sonnet 3.5 via Bedrock
   - Test tool calling

3. **Phase 3**: Build Streamlit UI
   - Transaction input form
   - Real-time analysis display
   - Alert dashboard
   - Report viewer

4. **Phase 4**: Integration & Testing
   - End-to-end testing with scenarios
   - Performance optimization
   - UI/UX refinement

5. **Phase 5**: EKS Deployment (Future)
   - Kubernetes manifests
   - Helm charts
   - Production configuration

### Demo Flow for Chalk Talk

1. **Opening** (2 min)
   - Show web UI
   - Explain financial fraud problem
   - Introduce the solution

2. **Live Demo** (5 min)
   - Enter suspicious transaction
   - Watch agent analyze in real-time
   - Show tools being called
   - Display fraud alert
   - Generate report

3. **Architecture Deep Dive** (3 min)
   - MCP servers architecture
   - Claude Sonnet tool calling
   - Why Bedrock > vLLM for tools

4. **Q&A** (Remaining time)

### Key Talking Points

- **MCP = Model Context Protocol**: Standard for AI tool integration
- **Claude Sonnet 3.5**: Superior tool calling vs other models
- **Real-time Fraud Detection**: Sub-second analysis
- **Scalability**: EKS + MCP architecture
- **Cost-Effective**: Pay per request with Bedrock
