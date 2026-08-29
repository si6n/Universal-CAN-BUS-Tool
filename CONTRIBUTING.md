# Contributing Guidelines

Welcome to the **Universal CAN-Bus Diagnostic & Telemetry Platform**! We welcome contributions to protocol decoders, hardware HAL drivers, and safety systems.

## Development Setup

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/<your-username>/Universal-CAN-Bus-Diagnostic.git
   cd Universal-CAN-Bus-Diagnostic
   ```

2. **Create Virtual Environment & Install Dependencies**:
   ```bash
   python -m venv venv
   venv\Scripts\activate   # On Windows
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

3. **Frontend Setup (Optional for UI Changes)**:
   ```bash
   cd src/ui/frontend
   npm install
   npm run build
   cd ../../..
   ```

## Code Quality & Safety Rules

- **Zero Unverified Transmissions**: Every frame transmission MUST be guarded by `TxSafetyGateway` and `SafetySupervisor`.
- **Fail-Silent & Safe-by-Default**: System must default to listen-only (PASSIVE) mode.
- **Run All 274 Tests**: All pull requests must pass the complete test suite:
  ```bash
  pytest
  ruff check .
  ```
