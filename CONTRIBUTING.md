# Contributing to Airweave

Thank you for your interest in contributing to Airweave! This document provides guidelines and instructions for contributing to the project.

## Getting Started

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/)
- Python 3.11+ (for backend development)
- Node.js 20+ (for frontend development)
- [Visual Studio Code](https://code.visualstudio.com/) (recommended for optimal development experience)

### Open Source Development Workflow

As this is an open source project, we follow the fork and pull request workflow:

1. Fork the repository on GitHub
2. Clone your fork locally
   ```bash
   git clone https://github.com/YOUR-USERNAME/airweave.git
   cd airweave
   ```

3. Add the original repository as upstream
   ```bash
   git remote add upstream https://github.com/airweave-ai/airweave.git
   ```

4. Create a new branch for your changes
   ```bash
   git checkout -b feature/your-feature-name
   ```

5. Make your changes and commit them
6. Push to your fork
   ```bash
   git push origin feature/your-feature-name
   ```

7. Open a pull request from your fork to the main repository

### Setup Development Environment

1. Setup pre-commit hooks
   ```bash
   pip install pre-commit
   pre-commit install
   ```

2. Initial setup with Docker
   ```bash
   ./start.sh
   ```

3. For ongoing development, we recommend using VS Code with our provided launch configurations:
   - Open the project in VS Code
   - Use the "Run and Debug" view (Ctrl+Shift+D or Cmd+Shift+D)
   - Select "FastAPI" configuration to run the backend
   - Select "Debug React" for frontend development
   - Use "FastAPI + ARQ Worker" compound launch for full stack development

   These launch configurations are more efficient for development than repeatedly using `./start.sh`.

## Development Workflow

### Code Structure

Airweave is a monorepo with:
- `backend/`: Python FastAPI application
- `frontend/`: React/TypeScript application

### Coding Standards

- **Backend**: We use [Ruff](https://github.com/astral-sh/ruff) for linting and formatting Python code
- **Frontend**: We use [ESLint](https://eslint.org/) and follow TypeScript best practices
- Pre-commit hooks will automatically check your code before committing

### Pull Request Process

1. Ensure your fork is up to date with the upstream repository
   ```bash
   git fetch upstream
   git merge upstream/main
   ```

2. Make your changes
3. Ensure all tests pass and linting checks pass
4. Submit a pull request to the main repository
5. Update the PR description with any relevant information
6. Respond to any feedback from maintainers

### Commit Messages

Follow conventional commit format for clear, consistent history:
```
type(scope): short summary

Optional longer description
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Example: `feat(sources): add support for Notion API`

## Testing

- **Backend**: Run `pytest` in the backend directory
- **Frontend**: Run `npm test` in the frontend directory
- Use the "Pytest Debug" launch configuration in VS Code for debugging tests

## Documentation

- Update documentation when changing functionality
- Document new features, APIs, and configuration options

## Need Help?

If you have any questions or need assistance, please:
- Open an issue for discussion
- Refer to existing documentation
- Contact the maintainers through appropriate channels

Thank you for contributing to Airweave!
