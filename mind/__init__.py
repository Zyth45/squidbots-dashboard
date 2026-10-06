"""The mind service: personas, memory and LLM routing for bots.

The worldserver module (a fork of mod-ollama-chat) posts OpenAI-style chat requests to a "gateway".
This package is that gateway. It knows who the bot is, adds the bot's persona and what it remembers
about the player, sends the request to whichever LLM is assigned, and remembers what was said.

Standard library only: it has to run on the Python that ships with the repack, with nothing installed.
"""
