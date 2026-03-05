"""CLI entry point for Meta-Agent system."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from meta_agent.config import load_config, MetaAgentConfig
from meta_agent.models.optimization import OptimizationConfig
from meta_agent.services.langfuse_client import LangfuseClient
from meta_agent.services.sunnyagent_client import SunnyAgentClient
from meta_agent.services.file_service import FileService
from meta_agent.services.dataset_service import DatasetService
from meta_agent.services.evaluation_service import EvaluationService
from meta_agent.utils.score_calculator import ScoreCalculator
from meta_agent.utils.git_utils import GitUtils
from meta_agent.agents.orchestrator import OrchestratorAgent
from meta_agent.agents.environment_setup import EnvironmentSetupAgent
from meta_agent.agents.evaluator import EvaluatorAgent
from meta_agent.agents.analyzer import AnalyzerAgent
from meta_agent.agents.generator import GeneratorAgent
from meta_agent.agents.reviewer import ReviewerAgent
from meta_agent.utils.report_generator import ReportGenerator


console = Console()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(console=console, rich_tracebacks=True)],
)
logger = logging.getLogger("meta_agent")


def get_base_dir() -> Path:
    """Get meta_agent base directory."""
    return Path(__file__).parent


def get_repo_root() -> Path:
    """Get repository root directory."""
    return Path(__file__).parent.parent


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
def cli(verbose: bool) -> None:
    """Meta-Agent Plugin Optimization System."""
    if verbose:
        logging.getLogger("meta_agent").setLevel(logging.DEBUG)


@cli.command()
@click.option("--config", "-c", "config_path", type=click.Path(), help="Config file path")
@click.option("--target-plugin", "-p", help="Target plugin name")
@click.option("--dataset", "-d", type=click.Path(), help="Dataset file path")
@click.option("--target-score", type=float, help="Target score (0-1)")
@click.option("--max-iterations", type=int, help="Maximum iterations")
@click.option("--dry-run", is_flag=True, help="Validate only, don't execute")
def optimize(
    config_path: str | None,
    target_plugin: str | None,
    dataset: str | None,
    target_score: float | None,
    max_iterations: int | None,
    dry_run: bool,
) -> None:
    """Run plugin optimization."""
    console.print("[bold blue]Meta-Agent Plugin Optimization[/bold blue]")

    # Load configuration
    config = load_config(config_path)

    if not config.optimization:
        if not target_plugin or not dataset:
            console.print(
                "[red]Error: Must provide --target-plugin and --dataset, "
                "or use a config file with optimization settings[/red]"
            )
            sys.exit(1)

        config.optimization = OptimizationConfig(
            target_plugin=target_plugin,
            dataset_path=dataset,
        )

    # Apply CLI overrides
    if target_plugin:
        config.optimization.target_plugin = target_plugin
    if dataset:
        config.optimization.dataset_path = dataset
    if target_score is not None:
        config.optimization.target_score = target_score
    if max_iterations is not None:
        config.optimization.max_iterations = max_iterations

    console.print(f"Target plugin: [cyan]{config.optimization.target_plugin}[/cyan]")
    console.print(f"Dataset: [cyan]{config.optimization.dataset_path}[/cyan]")
    console.print(f"Target score: [cyan]{config.optimization.target_score}[/cyan]")

    if dry_run:
        console.print("\n[yellow]Dry run mode - validating configuration only[/yellow]")
        # Validate dataset
        base_dir = get_base_dir()
        dataset_service = DatasetService(str(base_dir))
        try:
            ds = dataset_service.load_dataset(config.optimization.dataset_path)
            console.print(f"[green]✓ Dataset valid: {len(ds.cases)} cases[/green]")
        except Exception as e:
            console.print(f"[red]✗ Dataset validation failed: {e}[/red]")
            sys.exit(1)
        return

    # Run optimization
    asyncio.run(_run_optimization(config))


async def _run_optimization(config: MetaAgentConfig) -> None:
    """Run the optimization loop."""
    base_dir = get_base_dir()
    repo_root = get_repo_root()

    # Initialize services
    langfuse = LangfuseClient(
        public_key=config.langfuse.public_key,
        secret_key=config.langfuse.secret_key,
        base_url=config.langfuse.base_url,
    )

    sunnyagent = SunnyAgentClient(
        base_url=config.sunnyagent.base_url,
        admin_username=config.sunnyagent.admin_username,
        admin_password=config.sunnyagent.admin_password,
    )

    file_service = FileService(str(repo_root))
    dataset_service = DatasetService(str(base_dir), langfuse)
    score_calculator = ScoreCalculator()
    evaluation_service = EvaluationService(sunnyagent, langfuse, score_calculator)

    try:
        git_utils = GitUtils(str(repo_root))
    except Exception as e:
        console.print(f"[yellow]Warning: Git not available: {e}[/yellow]")
        git_utils = None

    # Initialize agents
    env_agent = EnvironmentSetupAgent(sunnyagent, str(base_dir))
    evaluator = EvaluatorAgent(evaluation_service)
    analyzer = AnalyzerAgent()
    generator = GeneratorAgent(file_service, git_utils) if git_utils else None
    reviewer = ReviewerAgent(file_service)

    if not generator:
        console.print("[red]Error: Git is required for optimization[/red]")
        sys.exit(1)

    orchestrator = OrchestratorAgent(
        config=config.optimization,
        environment_agent=env_agent,
        evaluator_agent=evaluator,
        analyzer_agent=analyzer,
        generator_agent=generator,
        reviewer_agent=reviewer,
        dataset_service=dataset_service,
        checkpoints_dir=str(base_dir / ".checkpoints"),
    )

    # Run optimization
    from meta_agent.agents.base import AgentContext

    context = AgentContext()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Running optimization...", total=None)
        result = await orchestrator.run(context)

    if result.success:
        console.print(f"\n[green]✓ Optimization complete![/green]")
        if result.data:
            console.print(f"Final score: [bold]{result.data.best_score:.2f}[/bold]")
            console.print(f"Iterations: [bold]{result.data.current_iteration}[/bold]")

            # Generate report
            report_gen = ReportGenerator(str(base_dir / "results"))
            report_path = report_gen.generate_final_report(result.data)
            console.print(f"Report: [cyan]{report_path}[/cyan]")
    else:
        console.print(f"\n[red]✗ Optimization failed: {result.error}[/red]")
        sys.exit(1)


@cli.command()
@click.argument("dataset_path", type=click.Path(exists=True))
def validate(dataset_path: str) -> None:
    """Validate a dataset file."""
    console.print(f"Validating: [cyan]{dataset_path}[/cyan]")

    base_dir = get_base_dir()
    dataset_service = DatasetService(str(base_dir))

    try:
        dataset = dataset_service.load_dataset(dataset_path)
        console.print(f"[green]✓ Dataset valid[/green]")
        console.print(f"  Name: {dataset.name}")
        console.print(f"  Plugin: {dataset.plugin_name}")
        console.print(f"  Cases: {len(dataset.cases)}")

        # Show case summary
        table = Table(title="Test Cases")
        table.add_column("ID")
        table.add_column("Command")
        table.add_column("Expected Skill")
        table.add_column("Files")

        for case in dataset.cases[:10]:
            table.add_row(
                case.case_id,
                case.command or "-",
                case.expected_skill or "-",
                str(len(case.context_files)),
            )

        if len(dataset.cases) > 10:
            table.add_row("...", "...", "...", "...")

        console.print(table)

    except Exception as e:
        console.print(f"[red]✗ Validation failed: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.argument("dataset_path", type=click.Path(exists=True))
def sync(dataset_path: str) -> None:
    """Sync dataset to Langfuse."""
    console.print(f"Syncing to Langfuse: [cyan]{dataset_path}[/cyan]")

    config = load_config()
    base_dir = get_base_dir()

    langfuse = LangfuseClient(
        public_key=config.langfuse.public_key,
        secret_key=config.langfuse.secret_key,
        base_url=config.langfuse.base_url,
    )

    dataset_service = DatasetService(str(base_dir), langfuse)

    async def _sync():
        dataset = dataset_service.load_dataset(dataset_path)
        dataset_id = await dataset_service.sync_to_langfuse(dataset)
        console.print(f"[green]✓ Synced to Langfuse[/green]")
        console.print(f"  Dataset ID: {dataset_id}")

    asyncio.run(_sync())


@cli.command()
@click.argument("dataset_path", type=click.Path(exists=True))
def evaluate(dataset_path: str) -> None:
    """Run evaluation only (no optimization)."""
    console.print(f"Evaluating: [cyan]{dataset_path}[/cyan]")

    config = load_config()
    asyncio.run(_run_evaluation(config, dataset_path))


async def _run_evaluation(config: MetaAgentConfig, dataset_path: str) -> None:
    """Run evaluation."""
    base_dir = get_base_dir()

    langfuse = LangfuseClient(
        public_key=config.langfuse.public_key,
        secret_key=config.langfuse.secret_key,
        base_url=config.langfuse.base_url,
    )

    sunnyagent = SunnyAgentClient(
        base_url=config.sunnyagent.base_url,
        admin_username=config.sunnyagent.admin_username,
        admin_password=config.sunnyagent.admin_password,
    )

    dataset_service = DatasetService(str(base_dir), langfuse)
    score_calculator = ScoreCalculator()
    evaluation_service = EvaluationService(sunnyagent, langfuse, score_calculator)

    # Load dataset
    dataset = dataset_service.load_dataset(dataset_path)
    console.print(f"Loaded {len(dataset.cases)} test cases")

    # Run evaluation
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Running evaluation...", total=None)
        result = await evaluation_service.run_evaluation(
            dataset=dataset,
            project_name="meta-agent-eval",
            iteration=0,
        )

    # Display results
    console.print(f"\n[bold]Evaluation Results[/bold]")
    console.print(f"Overall Score: [bold]{result.overall_score:.2f}[/bold]")
    console.print(f"Pass Rate: {result.pass_rate:.1%}")
    console.print(f"Passed: {result.passed_cases}/{result.total_cases}")

    if result.langfuse_dashboard_url:
        console.print(f"Langfuse: {result.langfuse_dashboard_url}")

    if result.failed_case_details:
        console.print(f"\n[bold]Failed Cases[/bold]")
        table = Table()
        table.add_column("Case ID")
        table.add_column("Category")
        table.add_column("Reason")

        for case in result.failed_case_details[:10]:
            table.add_row(
                case.case_id,
                case.failure_category.value,
                case.failure_reason[:50] + "..." if len(case.failure_reason) > 50 else case.failure_reason,
            )

        console.print(table)


@cli.command()
@click.argument("checkpoint_id")
def resume(checkpoint_id: str) -> None:
    """Resume optimization from checkpoint."""
    console.print(f"Resuming from checkpoint: [cyan]{checkpoint_id}[/cyan]")

    base_dir = get_base_dir()
    checkpoints_dir = str(base_dir / ".checkpoints")

    checkpoint = OrchestratorAgent.load_checkpoint(checkpoint_id, checkpoints_dir)
    if not checkpoint:
        console.print(f"[red]✗ Checkpoint not found: {checkpoint_id}[/red]")
        sys.exit(1)

    console.print(f"Plugin: {checkpoint.config.target_plugin}")
    console.print(f"Iteration: {checkpoint.current_iteration}")
    console.print(f"Best Score: {checkpoint.best_score:.2f}")

    # TODO: Implement resume logic
    console.print("[yellow]Resume not yet implemented[/yellow]")


@cli.group()
def checkpoints() -> None:
    """Manage optimization checkpoints."""
    pass


@checkpoints.command(name="list")
def checkpoints_list() -> None:
    """List all checkpoints."""
    base_dir = get_base_dir()
    checkpoints_dir = str(base_dir / ".checkpoints")

    items = OrchestratorAgent.list_checkpoints(checkpoints_dir)

    if not items:
        console.print("No checkpoints found")
        return

    table = Table(title="Checkpoints")
    table.add_column("ID")
    table.add_column("Plugin")
    table.add_column("Iteration")
    table.add_column("Score")
    table.add_column("State")
    table.add_column("Updated")

    for item in items:
        table.add_row(
            item["id"][:8] + "...",
            item["plugin"],
            str(item["iteration"]),
            f"{item['best_score']:.2f}",
            item["state"],
            item["updated_at"][:19] if item["updated_at"] else "-",
        )

    console.print(table)


@checkpoints.command(name="show")
@click.argument("checkpoint_id")
def checkpoints_show(checkpoint_id: str) -> None:
    """Show checkpoint details."""
    base_dir = get_base_dir()
    checkpoints_dir = str(base_dir / ".checkpoints")

    checkpoint = OrchestratorAgent.load_checkpoint(checkpoint_id, checkpoints_dir)
    if not checkpoint:
        console.print(f"[red]✗ Checkpoint not found: {checkpoint_id}[/red]")
        sys.exit(1)

    console.print(f"[bold]Checkpoint: {checkpoint.optimization_id}[/bold]")
    console.print(f"Plugin: {checkpoint.config.target_plugin}")
    console.print(f"State: {checkpoint.state.value}")
    console.print(f"Iteration: {checkpoint.current_iteration}")
    console.print(f"Best Score: {checkpoint.best_score:.2f} (iteration {checkpoint.best_iteration})")

    if checkpoint.score_history:
        console.print(f"\nScore History: {', '.join(f'{s:.2f}' for s in checkpoint.score_history)}")

    if checkpoint.modified_files:
        console.print(f"\nModified Files:")
        for mod in checkpoint.modified_files:
            console.print(f"  - {mod.file_path} ({mod.modification_type})")


if __name__ == "__main__":
    cli()
