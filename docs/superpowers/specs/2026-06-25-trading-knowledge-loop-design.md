# Trading Knowledge and Feedback Loop — Design

Date: 2026-06-25
Status: Approved for planning

## Purpose

Connect the Investment Agent project with the user's Obsidian knowledge base so that two things happen whenever the user chooses. First, the educational and decision content the agent already produces flows into the vault as durable, searchable notes. Second, the user's review of how the agent actually performed flows back into the agent as accumulated guidance, so each future run can make better decisions. The result is a closed loop: the agent teaches the vault, and the vault teaches the agent.

## Background

The Investment Agent is an AI paper trading bot. On each run it scans the market, scores candidates with technical indicators, asks Claude for buy and sell decisions, and saves the result. The saved result already contains a daily lesson, a market education summary, the trade decisions with reasoning, and a short briefing. The agent runs on a schedule on a server and syncs through a GitHub repository. The knowledge base is a separate Obsidian vault that syncs through iCloud and is not a git repository.

Two facts about the current data handling shape this design. The latest run result is written to a single file that is overwritten on every run, so only the most recent run is ever visible in it. The trade database that holds real outcomes is excluded from git, so it does not travel with a pull on the user's laptop. Both facts must be addressed for a weekly review and a real feedback loop to work.

## Goals

Capture the agent's daily lesson, market education, and trade decisions into the vault as well organized notes. Analyze how the agent's decisions turned out against real outcomes. Distill that analysis into plain guidance the agent can read on its next run. Keep the user in full control of when this happens and make every step transparent and reversible. Make the whole process safe to run either daily or weekly without creating duplicates or losing days.

## Non-goals

This design does not change the agent's trading logic, position sizing, or risk thresholds. It does not retrain any model. It does not capture the weekly performance digest into the vault for now, though that can be added later. It does not automate the trigger; the user runs it deliberately.

## Overview of components

There are three components spread across the two repositories. The first two are changes inside the Investment Agent project. The third is a new skill inside the vault.

## Component A — Daily journal archive in the project

The project gains a new step that runs at the end of each agent run. It writes one journal file per day into a dedicated journal folder under the data directory, named by date. Each journal file holds the day's daily lesson, the day's market education summary, the day's trade decisions with reasoning, and a snapshot of outcomes at that moment, meaning the portfolio total value, profit and loss, and the open positions. These journal files are tracked by git so that a pull on the user's laptop brings the complete history. This removes any dependence on the trade database for the review, because everything the review needs is captured in the journal at the time of the run. Writing a journal must never interrupt or fail an agent run; if it cannot write, it records the problem and the run continues.

## Component B — Strategy memory read by the agent

The project gains a strategy memory file in the data directory, written in plain language. The agent gains a small helper that reads this file at the start of building its prompt and returns nothing if the file is absent. The prompt builder injects the memory as a new clearly labeled section, presented to the agent as lessons learned from past performance that it should weigh when deciding. The memory is guidance, not a hard rule, so it never conflicts with the enforced risk rules. The helper and the new prompt section are covered by unit tests in the same style as the existing tests.

## Component C — The trading review skill in the vault

A new skill is added to the vault that the user runs by command. It is safe to run daily or weekly because it tracks which journal days it has already processed and skips them. The skill performs the following sequence.

It begins by pulling the project repository so it has the newest journal files. It then reads every journal day that has not yet been processed. For each day it writes vault notes. Daily lessons become one note per concept in a stock market glossary folder, where an existing concept is enriched rather than duplicated. Market education becomes one dated note in a market recaps folder, with links to any glossary concepts mentioned. Trade decisions become one dated note in a trades folder under the AI learning area, recording each decision with its conviction and reasoning.

After writing notes, the skill analyzes the decisions against the outcome snapshots in the journals. It looks for patterns that connect decisions to results, such as whether high conviction choices tended to succeed, whether stop losses fired repeatedly under particular conditions, or whether certain market directions led to poor entries. It distills these observations into a small number of clear, plain language lessons.

The skill then appends those lessons, dated, to the strategy memory file in the project. Finally it pushes the project repository so that the next scheduled agent run reads the updated memory. Both the pull at the start and the push at the end are scoped only to the project repository, because the vault itself is not a git repository.

## Data flow

An agent run produces a dated journal file that is committed in the project. When the user runs the review skill, it pulls the project to obtain the newest journals, writes the vault notes, analyzes outcomes, appends lessons to the strategy memory, and pushes the project. The next agent run reads the strategy memory and factors it into its decisions. The loop then repeats on the user's chosen cadence.

## Vault organization

Glossary notes live in a stock market glossary folder within the knowledge domains area. Market recap notes live in a market recaps folder within the same area. Trade notes live in a trades folder within an investment agent folder under the AI learning area. Knowledge that is general to the stock market sits in the knowledge domains area, while the record of the agent's own activity sits in the AI learning area.

## Language

Vault notes are written in English only, to match the rest of the vault, even though the agent also produces Traditional Chinese content. This can be revisited later if bilingual notes are wanted.

## Idempotency and safety

The review skill must produce the same result whether run daily or weekly, never creating duplicate notes and never losing a day. It achieves this by tracking processed journal days and by enriching existing glossary concepts instead of recreating them. Every git action is confined to the project repository. The journal writing step in the agent must be incapable of breaking a run. The strategy memory is plain text the user can read and edit at any time, so the user always retains control over what the agent is told.

## Decisions locked in

Capture covers daily lessons, market education, and trade decisions, and excludes the weekly performance digest for now. The learning mechanism is the strategy memory file as soft guidance, with no change to trading logic. Data is made reliable by dated journal archives rather than by committing the database or by relying on a single overwritten file. Git pull happens before work and git push happens after, scoped to the project only. Vault notes are English only.

## Open questions

None at this time.
