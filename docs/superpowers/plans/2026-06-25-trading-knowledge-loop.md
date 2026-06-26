# Trading Knowledge and Feedback Loop Implementation Plan

> For agentic workers: REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task by task. Steps use checkbox syntax for tracking.

Goal: Build a closed loop where the agent's daily output flows into the Obsidian vault as notes, and a user-run review distills performance lessons back into the agent's prompt.

Architecture: Two small additions to the Python project, the bot writes a dated journal file each run and the agent reads a strategy memory file injected into its prompt, plus one new Claudian skill in the vault that moves journal content into notes, analyzes outcomes, writes the memory file, and synchronizes the project repository with git.

Tech Stack: Python with pytest in the project repository, Markdown skill definition in the vault, git for synchronization of the project repository only.

Note on format: This plan is written in plain English with no code blocks, following the user's global documentation guideline. Each step still names the exact files, the exact behavior to build, the exact test to write described in words, and the exact command to run.

---

## File structure

In the project repository the work creates a journal writer module at agent/tools/journal.py with its test at tests/test_journal.py, creates a strategy memory loader module at agent/tools/strategy_memory.py with its test at tests/test_strategy_memory.py, modifies the run two command in agent/main.py to call the journal writer, modifies the prompt builder in agent/claude_agent.py to inject the strategy memory, and adds prompt builder coverage in the existing tests/test_claude_agent.py. The journal files are written under data/journal and the memory file is written at data/strategy_memory.md.

In the vault the work creates one skill definition at .claude/skills/trading-review/SKILL.md.

Each module has one clear responsibility. The journal writer only serializes a day's record. The memory loader only reads a file safely. The prompt builder change only adds one section. The skill only orchestrates the vault and git side.

---

## Task 1: Journal writer module

Files: create agent/tools/journal.py, create tests/test_journal.py.

The journal writer exposes one function that takes the decisions dictionary as produced by the agent, the portfolio status dictionary as produced by get_portfolio_status, a journal directory path, and a date string, and writes one file named by the date with a json extension into the journal directory. The written content holds the date, the daily lesson, the market education summary, the trades list with their reasoning and conviction, the briefing, and an outcomes snapshot containing total value, cash, profit and loss in dollars, profit and loss in percent, and the open positions. The function never raises; on any problem it returns a result describing failure, and on success it returns a result describing success and the path written. This mirrors the never-raises style already used by the dashboard sync helper.

- [ ] Step 1: Write the failing test. In tests/test_journal.py write a test that builds a sample decisions dictionary containing a daily lesson, a market education summary, and one buy trade, builds a sample portfolio dictionary with a total value and one open position, calls the journal writer with a temporary directory and the date string for the twenty fifth of June twenty twenty six, then asserts that a file named by that date with a json extension now exists in that directory, that its parsed contents contain the same daily lesson term and the same total value, and that the returned result indicates success.

- [ ] Step 2: Run the test and confirm it fails. Run pytest on tests/test_journal.py with verbose output. Expect failure because the module and function do not exist yet.

- [ ] Step 3: Write the minimal implementation in agent/tools/journal.py. Create the directory if needed, assemble the record described above from the two input dictionaries, write it as formatted json with readable unicode preserved, and return the success result. Wrap the body so that any exception is caught and returned as a failure result rather than raised.

- [ ] Step 4: Run the test and confirm it passes. Run pytest on tests/test_journal.py with verbose output. Expect a pass.

- [ ] Step 5: Add a second test for the never-raises guarantee. Write a test that calls the journal writer with a directory path that cannot be created, for example a path under a file rather than a folder, and asserts that the function returns a failure result and does not raise. Run the test and confirm it passes.

- [ ] Step 6: Commit. Stage agent/tools/journal.py and tests/test_journal.py and commit with a message describing the addition of the daily journal writer.

---

## Task 2: Hook the journal into run two

Files: modify agent/main.py within the run two command, extend tests/test_main.py.

The journal write happens at the very end of the run two command, after the daily snapshot is saved and the final portfolio status is read, so the snapshot reflects the post trade state. The decisions used are the ones loaded from the plan file earlier in run two. The call is wrapped so that a journal failure prints a warning and never interrupts the run, in the same way the dashboard export is wrapped. The journal directory is the data journal folder under the project root, consistent with how the plan path is computed.

- [ ] Step 1: Write the failing test. In tests/test_main.py add a test that runs the run two command against a temporary database and a temporary plan file whose decisions contain a daily lesson and an empty trades list, with market hours conditions handled the way existing run two tests handle them, and asserts that after the command completes a journal file for today exists under the expected journal directory. If existing tests already stub market hours or external calls, follow that same approach so the new test stays consistent.

- [ ] Step 2: Run the test and confirm it fails. Run pytest on the new test in tests/test_main.py with verbose output. Expect failure because no journal file is produced yet.

- [ ] Step 3: Add the journal call. In the run two command, after the final portfolio status read and snapshot save, import and call the journal writer with the loaded decisions, the final portfolio status, the data journal directory, and today's date string, and print a warning if the returned result indicates failure. Place this inside a guard so any unexpected error is caught and printed rather than propagated.

- [ ] Step 4: Run the test and confirm it passes. Run pytest on the new test in tests/test_main.py with verbose output. Expect a pass.

- [ ] Step 5: Run the full project test suite to confirm nothing regressed. Run pytest over the tests directory. Expect all tests to pass.

- [ ] Step 6: Commit. Stage agent/main.py and tests/test_main.py and commit with a message describing that run two now writes a daily journal.

---

## Task 3: Strategy memory loader module

Files: create agent/tools/strategy_memory.py, create tests/test_strategy_memory.py.

The loader exposes one function that takes a file path and returns the file's text content, or an empty string when the file is missing or unreadable. It never raises. This isolates all file reading concerns away from the prompt builder so the prompt builder stays simple and testable.

- [ ] Step 1: Write the failing test. In tests/test_strategy_memory.py write two tests. The first writes a short text into a temporary file, calls the loader on that path, and asserts the returned text equals what was written. The second calls the loader on a path that does not exist and asserts the returned value is an empty string and that no exception is raised.

- [ ] Step 2: Run the tests and confirm they fail. Run pytest on tests/test_strategy_memory.py with verbose output. Expect failure because the module and function do not exist yet.

- [ ] Step 3: Write the minimal implementation in agent/tools/strategy_memory.py. Read and return the file text inside a guard that returns an empty string on any exception.

- [ ] Step 4: Run the tests and confirm they pass. Run pytest on tests/test_strategy_memory.py with verbose output. Expect a pass.

- [ ] Step 5: Commit. Stage agent/tools/strategy_memory.py and tests/test_strategy_memory.py and commit with a message describing the addition of the strategy memory loader.

---

## Task 4: Inject strategy memory into the prompt

Files: modify agent/claude_agent.py within the prompt builder, extend tests/test_claude_agent.py.

The prompt builder gains an optional memory path argument that defaults to the data strategy memory file resolved relative to the project root. The builder calls the loader, and when the returned text is non empty it adds one new clearly labeled section near the top of the prompt, after the goal section, that presents the text as lessons learned from past performance to weigh when deciding. When the text is empty no section is added, so existing behavior is unchanged for users without a memory file. The new section is guidance and never claims to override the enforced risk rules.

- [ ] Step 1: Write the failing test. In tests/test_claude_agent.py add a test that writes a recognizable sentence into a temporary memory file, calls the prompt builder with representative market, portfolio, and screened stock inputs and with the memory path pointed at that file, and asserts that the recognizable sentence appears in the returned prompt and that a heading indicating lessons learned from past performance also appears. Add a second test that calls the prompt builder with the memory path pointed at a missing file and asserts that the lessons heading does not appear.

- [ ] Step 2: Run the tests and confirm they fail. Run pytest on the two new tests in tests/test_claude_agent.py with verbose output. Expect failure because the builder does not read memory yet.

- [ ] Step 3: Add the injection. In the prompt builder add the optional memory path argument with its default, call the loader, and conditionally build and include the lessons section only when the loaded text is non empty, inserting it into the ordered list of sections after the goal section.

- [ ] Step 4: Run the tests and confirm they pass. Run pytest on the two new tests in tests/test_claude_agent.py with verbose output. Expect a pass.

- [ ] Step 5: Run the full project test suite to confirm nothing regressed. Run pytest over the tests directory. Expect all tests to pass.

- [ ] Step 6: Commit. Stage agent/claude_agent.py and tests/test_claude_agent.py and commit with a message describing that the prompt now injects strategy memory.

---

## Task 5: The trading review skill in the vault

Files: create .claude/skills/trading-review/SKILL.md in the vault.

This skill is the orchestration layer the user runs by command. It is written as a skill definition with frontmatter giving it the name trading-review, a description explaining that it captures the agent's journal into notes and feeds lessons back to the agent, an argument hint indicating an optional time range, and the model invocation disabled so it only runs when the user calls it. The body describes the following ordered steps in plain language for the assistant to follow at run time.

First, synchronize input by running a git pull inside the project repository at the known project path, reporting the result and continuing only if the pull did not fail in a way that blocks reading.

Second, read the journal by listing every dated file under the project data journal folder, and determine which dates have not yet been turned into notes by checking whether the corresponding dated notes already exist in the vault, processing only the unprocessed dates so the skill is safe to run daily or weekly. If the user supplied a time range, restrict to journal dates within that range.

Third, write vault notes for each unprocessed date. For each daily lesson, create a note named by the concept inside the stock market glossary folder under the knowledge domains area, and if a note for that concept already exists, enrich it rather than create a duplicate. For each market education summary, create one dated note inside the market recaps folder under the same area, linking any glossary concepts mentioned. For the trades, create one dated note inside a trades folder within an investment agent folder under the AI learning area, recording each decision with its conviction and reasoning. All notes follow the vault's standard frontmatter and are written in English only.

Fourth, analyze outcomes by comparing the decisions in each journal against the outcomes snapshot, looking for patterns that connect decisions to results such as whether high conviction choices tended to succeed, whether stop losses fired repeatedly under particular conditions, or whether certain market directions led to poor entries, and distilling these into a small number of clear plain language lessons.

Fifth, update the agent memory by appending the distilled lessons, dated, to the strategy memory file in the project data folder, preserving any existing content so memory accumulates over time.

Sixth, synchronize output by staging the journal additions and the strategy memory file and committing and pushing the project repository, reporting the push result. All git actions are confined to the project repository because the vault is not a git repository.

Finally, present a short summary in the chat listing how many journal days were processed, how many glossary concepts were created or enriched, how many recap and trade notes were written, and how many lessons were added to memory.

- [ ] Step 1: Create the skill file with the frontmatter and the full ordered body described above, using the exact vault folder names from the design for glossary, market recaps, and trades, and using the exact project repository path and the project data journal and strategy memory locations.

- [ ] Step 2: Verify the skill is discoverable by listing the vault skills folder and confirming the trading-review skill file is present with valid frontmatter containing its name and description.

- [ ] Step 3: Note for the implementer that this skill cannot be unit tested like Python code, so verification is a manual dry run performed later with the user against real journal data, confirming notes appear in the right folders, the memory file gains a dated entry, and the project repository receives a commit.

---

## Task 6: Update project documentation

Files: modify README.md in the project repository.

- [ ] Step 1: Add a short section to the project README describing the daily journal archive under data journal, the strategy memory file under data and how the agent reads it, and the trading review skill that lives in the user's vault and drives the loop. Keep it to a few sentences consistent with the README's existing tone.

- [ ] Step 2: Commit. Stage README.md and commit with a message describing the documentation update for the knowledge and feedback loop.

---

## Self-review notes

Spec coverage check. Component A daily journal archive is covered by Tasks 1 and 2. Component B strategy memory read by the agent is covered by Tasks 3 and 4. Component C the trading review skill including git pull first and git push last scoped to the project repository is covered by Task 5. The idempotency requirement is satisfied by checking for existing dated notes before processing a journal date. The English only notes requirement and the standard frontmatter requirement are stated in Task 5. The no change to trading logic requirement holds because no task touches sizing or risk thresholds. Documentation is covered by Task 6.

Consistency check. The journal writer function is created in Task 1 and called in Task 2 with the same inputs, the loader is created in Task 3 and called in Task 4, and the strategy memory file path is the same location in Tasks 4 and 5. The journal folder location is the same in Tasks 1, 2, and 5.
