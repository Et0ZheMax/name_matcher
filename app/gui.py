from __future__ import annotations

import queue
import threading
import traceback
from pathlib import Path
from tkinter import END, BooleanVar, StringVar, Text, Tk, filedialog, messagebox
from tkinter import ttk

from app.exporter import export_result
from app.gui_helpers import make_default_output_path, open_path, parse_limit
from app.gui_state import ErrorEvent, GuiRunConfig, LogEvent, ProgressEvent, SuccessEvent
from app.pipeline.bootstrap import build_runtime


class PipelineWorker:
    def __init__(self, config: GuiRunConfig, event_queue: "queue.Queue[object]") -> None:
        self.config = config
        self.event_queue = event_queue

    def run(self) -> None:
        try:
            runtime = build_runtime(
                self.config.mode,
                no_cache=self.config.no_cache,
                debug=self.config.debug,
                log_callback=self._on_log,
            )
            if self.config.resume:
                runtime.runner.logger.info("Resume mode enabled: using cached source responses where available.")

            result = runtime.runner.run(
                self.config.input_path,
                org_column=self.config.org_column,
                first_column_as_org=self.config.first_column_as_org,
                limit=self.config.limit,
                progress_callback=self._on_progress,
            )
            export_result(result, self.config.output_path)
            runtime.runner.logger.info("Done. Output written to %s", self.config.output_path)
            self.event_queue.put(SuccessEvent(kind="success", result=result, output_path=self.config.output_path))
        except Exception as exc:
            self.event_queue.put(ErrorEvent(kind="error", message=str(exc), traceback_text=traceback.format_exc()))

    def _on_log(self, level: str, message: str) -> None:
        self.event_queue.put(LogEvent(kind="log", level=level, message=message))

    def _on_progress(self, idx: int, total: int, org: str) -> None:
        self.event_queue.put(ProgressEvent(kind="progress", idx=idx, total=total, organization=org))


class GuiApp:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("Org Name Enricher")
        self.root.geometry("980x760")
        self.root.minsize(900, 700)

        self.events: "queue.Queue[object]" = queue.Queue()
        self.worker_thread: threading.Thread | None = None
        self.last_output_path: Path | None = None
        self.last_logs_dir: Path | None = None

        self.input_var = StringVar()
        self.output_var = StringVar()
        self.org_column_var = StringVar()
        self.mode_var = StringVar(value="balanced")
        self.limit_var = StringVar()
        self.first_col_var = BooleanVar(value=True)
        self.no_cache_var = BooleanVar(value=False)
        self.resume_var = BooleanVar(value=False)
        self.debug_var = BooleanVar(value=False)

        self.progress_value_var = StringVar(value="0 / 0")
        self.current_org_var = StringVar(value="—")
        self.summary_var = StringVar(value="Готов к запуску")

        self._build_ui()
        self.root.after(100, self._poll_events)

    def _build_ui(self) -> None:
        container = ttk.Frame(self.root, padding=12)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)

        input_frame = ttk.LabelFrame(container, text="Входные данные", padding=10)
        input_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        input_frame.columnconfigure(0, weight=1)
        ttk.Entry(input_frame, textvariable=self.input_var).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(input_frame, text="Обзор…", command=self._choose_input).grid(row=0, column=1)

        output_frame = ttk.LabelFrame(container, text="Выходные данные", padding=10)
        output_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        output_frame.columnconfigure(0, weight=1)
        ttk.Entry(output_frame, textvariable=self.output_var).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(output_frame, text="Сохранить как…", command=self._choose_output).grid(row=0, column=1)

        params_frame = ttk.LabelFrame(container, text="Параметры", padding=10)
        params_frame.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        for col in range(4):
            params_frame.columnconfigure(col, weight=1 if col in (1, 3) else 0)

        ttk.Label(params_frame, text="Org column").grid(row=0, column=0, sticky="w")
        ttk.Entry(params_frame, textvariable=self.org_column_var).grid(row=0, column=1, sticky="ew", padx=(6, 12))
        ttk.Checkbutton(params_frame, text="Использовать первый столбец", variable=self.first_col_var).grid(
            row=0, column=2, columnspan=2, sticky="w"
        )

        ttk.Label(params_frame, text="Mode").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Combobox(
            params_frame,
            textvariable=self.mode_var,
            values=("strict", "balanced", "aggressive"),
            state="readonly",
        ).grid(row=1, column=1, sticky="ew", padx=(6, 12), pady=(8, 0))

        ttk.Label(params_frame, text="Limit").grid(row=1, column=2, sticky="w", pady=(8, 0))
        ttk.Entry(params_frame, textvariable=self.limit_var).grid(row=1, column=3, sticky="ew", pady=(8, 0))

        ttk.Checkbutton(params_frame, text="Без кэша", variable=self.no_cache_var).grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Checkbutton(params_frame, text="Resume", variable=self.resume_var).grid(row=2, column=1, sticky="w", pady=(8, 0))
        ttk.Checkbutton(params_frame, text="Debug", variable=self.debug_var).grid(row=2, column=2, sticky="w", pady=(8, 0))

        run_frame = ttk.LabelFrame(container, text="Запуск", padding=10)
        run_frame.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        self.start_button = ttk.Button(run_frame, text="Старт", command=self._start_run)
        self.start_button.grid(row=0, column=0, padx=(0, 8))
        self.open_result_button = ttk.Button(run_frame, text="Открыть результат", command=self._open_result, state="disabled")
        self.open_result_button.grid(row=0, column=1, padx=(0, 8))
        self.open_output_dir_button = ttk.Button(run_frame, text="Открыть папку результата", command=self._open_output_dir, state="disabled")
        self.open_output_dir_button.grid(row=0, column=2, padx=(0, 8))
        self.open_logs_button = ttk.Button(run_frame, text="Открыть логи", command=self._open_logs, state="disabled")
        self.open_logs_button.grid(row=0, column=3)

        status_frame = ttk.LabelFrame(container, text="Статус", padding=10)
        status_frame.grid(row=4, column=0, sticky="ew", pady=(0, 8))
        status_frame.columnconfigure(0, weight=1)
        self.progress = ttk.Progressbar(status_frame, orient="horizontal", mode="determinate")
        self.progress.grid(row=0, column=0, sticky="ew")
        ttk.Label(status_frame, textvariable=self.progress_value_var).grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Label(status_frame, text="Текущая организация:").grid(row=2, column=0, sticky="w", pady=(6, 0))
        ttk.Label(status_frame, textvariable=self.current_org_var).grid(row=3, column=0, sticky="w")
        ttk.Label(status_frame, textvariable=self.summary_var).grid(row=4, column=0, sticky="w", pady=(6, 0))

        logs_frame = ttk.LabelFrame(container, text="Логи", padding=10)
        logs_frame.grid(row=5, column=0, sticky="nsew")
        container.rowconfigure(5, weight=1)
        logs_frame.columnconfigure(0, weight=1)
        logs_frame.rowconfigure(0, weight=1)
        self.log_text = Text(logs_frame, height=16, wrap="word")
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(logs_frame, orient="vertical", command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.configure(state="disabled")
        self.log_text.tag_configure("INFO", foreground="#1f2937")
        self.log_text.tag_configure("WARNING", foreground="#b45309")
        self.log_text.tag_configure("ERROR", foreground="#b91c1c")

    def _choose_input(self) -> None:
        selected = filedialog.askopenfilename(
            title="Выберите входной файл",
            filetypes=[("Tabular files", "*.xlsx *.xls *.csv"), ("All files", "*.*")],
        )
        if not selected:
            return
        self.input_var.set(selected)
        if not self.output_var.get().strip():
            self.output_var.set(str(make_default_output_path(Path(selected))))

    def _choose_output(self) -> None:
        selected = filedialog.asksaveasfilename(
            title="Сохранить результат как",
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx"), ("CSV", "*.csv"), ("All files", "*.*")],
        )
        if selected:
            self.output_var.set(selected)

    def _build_config(self) -> GuiRunConfig:
        input_raw = self.input_var.get().strip()
        if not input_raw:
            raise ValueError("Укажите входной файл")

        input_path = Path(input_raw)
        if not input_path.exists() or not input_path.is_file():
            raise ValueError("Входной файл не найден")

        output_raw = self.output_var.get().strip()
        output_path = Path(output_raw) if output_raw else make_default_output_path(input_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.suffix.lower() not in {".xlsx", ".csv"}:
            output_path = output_path.with_suffix(".xlsx")

        limit = parse_limit(self.limit_var.get())
        org_column = self.org_column_var.get().strip() or None

        return GuiRunConfig(
            input_path=input_path,
            output_path=output_path,
            mode=self.mode_var.get(),
            org_column=org_column,
            first_column_as_org=self.first_col_var.get(),
            limit=limit,
            no_cache=self.no_cache_var.get(),
            resume=self.resume_var.get(),
            debug=self.debug_var.get(),
        )

    def _set_running_state(self, is_running: bool) -> None:
        self.start_button.configure(state="disabled" if is_running else "normal")

    def _start_run(self) -> None:
        try:
            cfg = self._build_config()
        except Exception as exc:
            messagebox.showerror("Ошибка параметров", str(exc))
            return

        self.output_var.set(str(cfg.output_path))
        self.summary_var.set("Выполняется...")
        self.progress.configure(value=0, maximum=1)
        self.progress_value_var.set("0 / 0")
        self.current_org_var.set("—")
        self.open_result_button.configure(state="disabled")
        self.open_output_dir_button.configure(state="disabled")

        self._append_log("INFO", f"Starting run: input={cfg.input_path} output={cfg.output_path}")
        self._set_running_state(True)

        self.worker_thread = threading.Thread(target=PipelineWorker(cfg, self.events).run, daemon=True)
        self.worker_thread.start()

    def _append_log(self, level: str, message: str) -> None:
        self.log_text.configure(state="normal")
        tag = level if level in {"INFO", "WARNING", "ERROR"} else "INFO"
        self.log_text.insert(END, message + "\n", tag)
        self.log_text.see(END)
        self.log_text.configure(state="disabled")

    def _poll_events(self) -> None:
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            self._handle_event(event)
        self.root.after(100, self._poll_events)

    def _handle_event(self, event: object) -> None:
        if isinstance(event, LogEvent):
            self._append_log(event.level, event.message)
            return
        if isinstance(event, ProgressEvent):
            self.progress.configure(maximum=max(event.total, 1), value=event.idx)
            self.progress_value_var.set(f"{event.idx} / {event.total}")
            self.current_org_var.set(event.organization)
            return
        if isinstance(event, SuccessEvent):
            self.last_output_path = event.output_path
            self.last_logs_dir = Path("logs")
            manual = len(event.result.manual_review)
            total = len(event.result.organizations)
            self.summary_var.set(
                f"Успешно: обработано {total}, manual review {manual}. Файл: {event.output_path}"
            )
            self._set_running_state(False)
            if event.output_path.exists():
                self.open_result_button.configure(state="normal")
                self.open_output_dir_button.configure(state="normal")
            self.open_logs_button.configure(state="normal")
            return
        if isinstance(event, ErrorEvent):
            self._append_log("ERROR", event.traceback_text)
            self.summary_var.set("Запуск завершился с ошибкой")
            self._set_running_state(False)
            self.open_logs_button.configure(state="normal")
            messagebox.showerror("Ошибка выполнения", event.message)

    def _open_result(self) -> None:
        if self.last_output_path and self.last_output_path.exists():
            open_path(self.last_output_path)

    def _open_output_dir(self) -> None:
        if self.last_output_path:
            open_path(self.last_output_path.parent)

    def _open_logs(self) -> None:
        logs_dir = self.last_logs_dir or Path("logs")
        logs_dir.mkdir(parents=True, exist_ok=True)
        open_path(logs_dir)


def main() -> None:
    root = Tk()
    GuiApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
