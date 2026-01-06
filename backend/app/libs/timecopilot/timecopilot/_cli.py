import asyncio
import contextlib
import io
import sys
from pathlib import Path

import logfire
import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.status import Status

from timecopilot.agent import AsyncTimeCopilot
from timecopilot.agent import TimeCopilot as TimeCopilotAgent

logfire.configure(send_to_logfire="if-token-present")
logfire.instrument_pydantic_ai()


class TimeCopilot:
    def __init__(self):
        self.console = Console()

    @contextlib.contextmanager
    def _capture_prints_static(self):
        """Capture print statements and format them nicely."""
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        try:
            sys.stdout = stdout_capture
            sys.stderr = stderr_capture
            yield
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

            # Process captured output
            stdout_content = stdout_capture.getvalue().strip()
            stderr_content = stderr_capture.getvalue().strip()

            if stdout_content:
                # Format as subdued info
                for line in stdout_content.split("\n"):
                    if line.strip():
                        self.console.print(f"[dim]  → {line}[/dim]")

            if stderr_content:
                # Format as subdued warning
                for line in stderr_content.split("\n"):
                    if line.strip():
                        self.console.print(f"[dim yellow]  ⚠ {line}[/dim yellow]")

    def forecast(
        self,
        path: str | Path,
        llm: str = "openai:gpt-4o-mini",
        freq: str | None = None,
        h: int | None = None,
        seasonality: int | None = None,
        query: str | None = None,
        retries: int = 3,
    ):
        with (
            self.console.status(
                "[bold blue]TimeCopilot is navigating through time...[/bold blue]"
            ),
            self._capture_prints_static(),
        ):
            forecasting_agent = TimeCopilotAgent(llm=llm, retries=retries)
            result = forecasting_agent.analyze(
                df=path,
                freq=freq,
                h=h,
                seasonality=seasonality,
                query=query,
            )

        result.output.prettify(
            self.console,
            features_df=result.features_df,
            eval_df=result.eval_df,
            fcst_df=result.fcst_df,
        )


class InteractiveChat:
    """Simplified interactive chat for TimeCopilot."""

    def __init__(self, llm: str = "openai:gpt-4o-mini"):
        self.llm = llm
        self.agent: AsyncTimeCopilot | None = None
        self.console = Console()

    @contextlib.contextmanager
    def _capture_prints(self):
        """Capture print statements and format them nicely."""
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        try:
            sys.stdout = stdout_capture
            sys.stderr = stderr_capture
            yield
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

            # Process captured output
            stdout_content = stdout_capture.getvalue().strip()
            stderr_content = stderr_capture.getvalue().strip()

            if stdout_content:
                # Format as subdued info
                for line in stdout_content.split("\n"):
                    if line.strip():
                        self.console.print(f"[dim]  → {line}[/dim]")

            if stderr_content:
                # Format as subdued warning
                for line in stderr_content.split("\n"):
                    if line.strip():
                        self.console.print(f"[dim yellow]  ⚠ {line}[/dim yellow]")

    def _print_welcome(self):
        """Print welcome message and instructions."""
        welcome_text = """
# 👋 Hi there! I'm TimeCopilot, the GenAI Forecasting Agent!

I'm here to help you understand your data and predict the future. Just talk to me 
naturally - no complex commands needed! I can seamlessly work with different models 
and explain why forecasts look the way they do, not just give you numbers.

## 💭 **Natural conversation examples:**
- "I have sales data at /path/to/sales.csv, forecast the next 6 months"
- "Can you spot any weird patterns in my server data?"
- "Show me a plot of the forecast you just created"
- "Why does this forecast look different from the previous one?"
- "What should I expect for user engagement next month?"
- "How confident are you about next week's predictions?"
- "Compare Chronos and TimesFM models for my dataset"

## 🎯 **Try saying:**
- "Forecast this dataset: /path/to/sales_data.csv"
- "Analyze anomalies in s3://bucket/server-metrics.csv"
- "What will my website traffic look like next month?"
- "Show me a plot of the forecast vs actual values"
- "Which forecasting model gives the most accurate results?"

The same workflow can be used for monitoring as well as forecasting.  
Ready to dive into your data? Just tell me what you'd like to explore! 🚀
        """

        panel = Panel(
            Markdown(welcome_text),
            title="[bold blue]Welcome to TimeCopilot[/bold blue]",
            border_style="blue",
            padding=(1, 2),
        )
        self.console.print(panel)

    def _extract_file_path(self, user_input: str) -> str | None:
        """Extract file path from user input."""
        words = user_input.split()
        for word in words:
            if (
                word.endswith(".csv")
                or word.endswith(".parquet")
                or word.startswith("http")
                or "/" in word
                or "\\" in word
            ):
                return word
        return None

    async def _handle_command(self, user_input: str) -> bool:
        """Handle user command. Returns False to exit."""
        user_input_lower = user_input.strip().lower()

        # Handle exit commands
        if user_input_lower in ["exit", "quit", "bye"]:
            return False

        # Handle help
        if user_input_lower in ["help", "?"]:
            self._print_welcome()
            return True

        # Check if we have an agent and can query
        if self.agent and self.agent.is_queryable():
            # Agent is ready for follow-up queries
            try:
                with (
                    Status(
                        "[bold blue]TimeCopilot is thinking...[/bold blue]",
                        console=self.console,
                    ),
                    self._capture_prints(),
                ):
                    result = await self.agent.query(user_input)

                # Display result
                response_panel = Panel(
                    result.output,
                    title="[bold cyan]TimeCopilot Response[/bold cyan]",
                    border_style="cyan",
                    padding=(1, 2),
                )
                self.console.print(response_panel)

            except Exception as e:
                self.console.print(f"[bold red]Error:[/bold red] {e}")
        else:
            # Handle initial data loading
            file_path = self._extract_file_path(user_input)

            if file_path:
                try:
                    # Create agent if needed
                    if not self.agent:
                        self.agent = AsyncTimeCopilot(llm=self.llm)

                    # Run analysis
                    with (
                        Status(
                            "[bold blue]Loading data and analyzing...[/bold blue]",
                            console=self.console,
                        ),
                        self._capture_prints(),
                    ):
                        result = await self.agent.analyze(
                            df=file_path, query=user_input
                        )

                    # Display conversational summary
                    selected_model = getattr(result.output, "selected_model", "Unknown")
                    horizon = (
                        len(getattr(result, "fcst_df", []))
                        if hasattr(result, "fcst_df")
                        else 0
                    )
                    beats_naive = getattr(
                        result.output, "is_better_than_seasonal_naive", False
                    )
                    performance_msg = (
                        "performing well" if beats_naive else "needs improvement"
                    )

                    self.console.print(
                        "\n[bold green]Great! I've completed the analysis.[/bold green]"
                    )
                    self.console.print(
                        f"[cyan]Selected Model:[/cyan] {selected_model} "
                        f"({performance_msg})"
                    )

                    if horizon > 0:
                        self.console.print(
                            f"[cyan]Forecast:[/cyan] Generated {horizon} future periods"
                        )

                    # Check for anomalies
                    if (
                        hasattr(result, "anomalies_df")
                        and result.anomalies_df is not None
                    ):
                        anomaly_cols = [
                            col
                            for col in result.anomalies_df.columns
                            if col.endswith("-anomaly")
                        ]
                        total_anomalies = sum(
                            result.anomalies_df[col].sum() for col in anomaly_cols
                        )
                        if total_anomalies > 0:
                            total_points = len(result.anomalies_df)
                            anomaly_rate = (total_anomalies / total_points) * 100
                            self.console.print(
                                f"[red]Found {total_anomalies} anomalies "
                                f"({anomaly_rate:.1f}%)[/red]"
                            )
                            self.console.print(
                                "[dim yellow]So the same workflow can be used for "
                                "monitoring as well as forecasting.[/dim yellow]"
                            )
                    # User response
                    user_response = result.output.user_query_response
                    if user_response:
                        response_panel = Panel(
                            user_response,
                            title="[bold cyan]TimeCopilot Response[/bold cyan]",
                            border_style="cyan",
                            padding=(1, 2),
                        )
                        self.console.print(response_panel)

                    self.console.print(
                        "\n[dim]💡 Try: 'show me the plot', 'explain this', "
                        "or try a different model[/dim]"
                    )

                except Exception as e:
                    self.console.print(f"[bold red]Error loading data:[/bold red] {e}")
            else:
                self.console.print(
                    "[bold yellow]Please provide a file path or URL to get started."
                    "[/bold yellow]"
                )
                self.console.print("[dim]Example: forecast /path/to/data.csv[/dim]")

        return True

    async def run(self):
        """Run the interactive chat session."""
        self._print_welcome()

        try:
            while True:
                try:
                    user_input = Prompt.ask(
                        "\n[bold blue]TimeCopilot[/bold blue]", default=""
                    )
                except KeyboardInterrupt:
                    self.console.print(
                        "\n[yellow]Interrupted. Type 'exit' to quit.[/yellow]"
                    )
                    continue

                if not user_input.strip():
                    continue

                should_continue = await self._handle_command(user_input)
                if not should_continue:
                    break

        except KeyboardInterrupt:
            pass
        finally:
            self.console.print(
                "\n[bold blue]👋 Thanks for using TimeCopilot! "
                "See you next time![/bold blue]"
            )


app = typer.Typer(
    name="timecopilot",
    help="TimeCopilot - Your GenAI Forecasting Agent",
    rich_markup_mode="rich",
    no_args_is_help=False,
)


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    llm: str = typer.Option(
        "openai:gpt-4o-mini", "--llm", "-l", help="LLM to use for the agent"
    ),
):
    """
    TimeCopilot - Your GenAI Forecasting Agent

    Just run 'timecopilot' to start chatting with your AI forecasting companion!
    Talk naturally about your data and get intelligent predictions and insights.
    """
    if ctx.invoked_subcommand is None:
        chat = InteractiveChat(llm=llm)
        asyncio.run(chat.run())


@app.command("forecast")
def forecast_command(
    path: str = typer.Argument(..., help="Path to CSV file or URL"),
    llm: str = typer.Option(
        "openai:gpt-4o-mini", "--llm", "-l", help="LLM to use for forecasting"
    ),
    freq: str = typer.Option(None, "--freq", "-f", help="Data frequency"),
    h: int = typer.Option(None, "--horizon", "-h", help="Forecast horizon"),
    seasonality: int = typer.Option(None, "--seasonality", "-s", help="Seasonality"),
    query: str = typer.Option(None, "--query", "-q", help="Additional query"),
    retries: int = typer.Option(3, "--retries", "-r", help="Number of retries"),
):
    """Generate forecast (legacy one-shot mode)."""
    tc = TimeCopilot()
    tc.forecast(
        path=path,
        llm=llm,
        freq=freq,
        h=h,
        seasonality=seasonality,
        query=query,
        retries=retries,
    )


def main():
    app()


if __name__ == "__main__":
    main()
