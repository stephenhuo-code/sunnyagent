# Meta-Agent Plugin Optimization System

A system for automatically optimizing SunnyAgent Plugin Commands and Skills through iterative evaluation using Langfuse datasets and Claude Agent Team architecture.

## Overview

Meta-Agent uses a team of specialized AI agents to:

1. **Evaluate** plugin commands/skills against test datasets
2. **Analyze** failure patterns and identify improvement opportunities
3. **Generate** optimized prompts and workflows
4. **Review** changes before applying them
5. **Iterate** until quality targets are met

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Orchestrator Agent                    │
│         (Coordinates optimization workflow)              │
└─────────────────────────────────────────────────────────┘
                           │
       ┌───────────────────┼───────────────────┐
       ▼                   ▼                   ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Evaluator  │    │  Analyzer   │    │  Generator  │
│   Agent     │    │   Agent     │    │   Agent     │
└─────────────┘    └─────────────┘    └─────────────┘
       │                   │                   │
       └───────────────────┼───────────────────┘
                           ▼
                   ┌─────────────┐
                   │  Reviewer   │
                   │   Agent     │
                   └─────────────┘
```

## Installation

```bash
cd meta_agent
uv sync
```

## Quick Start

### 1. Validate Plugin Structure

```bash
meta-agent validate --plugin manufacturing-qc
```

### 2. Sync Dataset to Langfuse

```bash
meta-agent sync --dataset test-resources/datasets/qc-tests.jsonl --plugin manufacturing-qc
```

### 3. Run Evaluation

```bash
meta-agent evaluate --plugin manufacturing-qc --dataset qc-tests
```

### 4. Run Full Optimization

```bash
meta-agent optimize --plugin manufacturing-qc --dataset qc-tests --target-score 0.85
```

### 5. Resume Interrupted Optimization

```bash
meta-agent resume <checkpoint-id>
```

## Configuration

Create a `config.yaml` file or use environment variables:

```yaml
langfuse:
  base_url: http://localhost:3001
  public_key: ${LANGFUSE_PUBLIC_KEY}
  secret_key: ${LANGFUSE_SECRET_KEY}

sunnyagent:
  base_url: http://localhost:8008
  username: admin
  password: ${SUNNYAGENT_PASSWORD}

anthropic:
  api_key: ${ANTHROPIC_API_KEY}
  model: claude-sonnet-4-20250514

optimization:
  target_score: 0.85
  max_iterations: 5
  checkpoint_dir: .checkpoints
```

## Score Calculation

The evaluation score is calculated as:

| Metric | Weight | Description |
|--------|--------|-------------|
| Correctness | 50% | Expected keywords/patterns in response |
| Skill Trigger | 16.7% | Correct skill was invoked |
| Response Quality | 16.7% | LLM-judged response quality |
| File Context Usage | 16.7% | Required files were used |

**Overall Score** = 0.50 × correctness + 0.167 × skill_trigger + 0.167 × response_quality + 0.167 × file_context_usage

## Dataset Format

Datasets use JSONL format with the following fields:

```jsonl
{"case_id": "qc_001", "input": "/analyze quality.csv", "expected_behavior": "分析质量数据并计算CPK", "expected_skill": "data-profiler", "expected_contains": ["CPK", "合格率"], "context_files": ["quality.csv"]}
```

## Project Structure

```
meta_agent/
├── agents/           # Claude Agent Team
│   ├── orchestrator.py
│   ├── evaluator.py
│   ├── analyzer.py
│   ├── generator.py
│   └── reviewer.py
├── models/           # Pydantic data models
│   ├── dataset.py
│   ├── evaluation.py
│   ├── optimization.py
│   └── plugin.py
├── services/         # External integrations
│   ├── langfuse_client.py
│   ├── sunnyagent_client.py
│   ├── file_service.py
│   ├── dataset_service.py
│   └── evaluation_service.py
├── utils/            # Utilities
│   ├── score_calculator.py
│   ├── git_utils.py
│   └── report_generator.py
├── config.py         # Configuration loading
├── config.yaml       # Default configuration
└── main.py           # CLI entry point
```

## Development

### Run Tests

```bash
uv run pytest tests/ -v
```

### Type Checking

```bash
uv run pyright
```

## License

Internal use only.
