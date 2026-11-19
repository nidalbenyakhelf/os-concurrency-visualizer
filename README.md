# OS Concurrency Visualizer

An interactive learning tool built in **Python** to visualize multi-producer, multi-consumer synchronization using a bounded buffer and semaphores (`empty`, `full`, `mutex`), complete with simulation controls (`Play`, `Pause`, `Step Forward`) and an integrated assistant.

## Project Structure

- `core/simulation.py`: Bounded buffer, semaphores, thread states (`RUNNING` / `BLOCKED`), speed controls, and step execution.
- `assistant/`: Natural language command parser and operating system concurrency explanations.
- `ui/`: Visual representation of the buffer, thread states, controls, and chat panel.
- `server.py` & `main.py`: Entry point and bridge between Python logic and the UI.

## Status

Work in progress — modular open-source build.
