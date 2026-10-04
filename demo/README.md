# Demo props

Three pages for the demo day walkthrough (ticket → Inspect View transcript → Falco console → live response), built from the example evidence. `ticket.html` is a made-up SOC queue for the fictional Kestrel Analytics. `falco.html` is a console for the Falco alerts in `examples/evidence/host/falco.jsonl`. `terminal.html` is a fake remote shell on ci-runner-01; press Enter to run `ls -la /srv/agent-output`, which prints `examples/evidence/host/agent-output-listing.txt` verbatim.

All three are self-contained, with the evidence embedded verbatim and no network requests. Double-click a file to open it in a browser; the app's preview pane doesn't run their scripts. Each ticket has buttons for all three tools. **Open in Inspect** links to Inspect View at http://127.0.0.1:7575, so start it first with `inspect view --log-dir examples/evidence/transcripts`. Edits live in memory only and reset when you reload.

`index.html` is the About page for the hosted copy. `python tools/build_site.py` builds that copy into `site/`: it adds a banner to each page, points Open in Inspect at a bundled Inspect View, and needs `inspect-ai==0.3.272`.
