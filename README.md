# Paper Trail

**Did they actually do what they promised?**

Paper Trail reads a municipality's climate strategy, pulls out every
commitment with a verbatim receipt, hunts for evidence in the official
sources of whoever owns the asset, and hands it all to a person to review.
The software only suggests: nothing reaches the public record until
someone clicks Confirm, and a commitment with no evidence shows up as a gap.

```sh
make setup && make dev     # api on :8000, ui on :3000, fully offline by default
make check                 # what ci runs
```

Everything else (how it works, the audit rules, running, deploying, the
models, the database, every setting) is in the
**[wiki](https://github.com/unnobatroo/paper-trail/wiki)**.

[Contributing](https://github.com/unnobatroo/paper-trail/wiki/Contributing) ·
[Security](SECURITY.md) · [Code of Conduct](CODE_OF_CONDUCT.md) ·
[GPL-3.0](LICENSE)
