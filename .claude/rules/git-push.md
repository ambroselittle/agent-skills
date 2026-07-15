## Pushing branches that touch `.github/workflows/`

HTTPS pushes to GitHub authenticate with the `gh` OAuth token, which must carry the `workflow` scope to create or update any file under `.github/workflows/`. A default `gh` login (`gist, read:org, repo`) lacks it, so a push that includes a workflow change is rejected:

```
! [remote rejected] refusing to allow an OAuth App to create or update workflow `.github/workflows/ci.yml` without `workflow` scope
```

**This rejection is a legitimate GitHub protection, not an obstacle to route around on your own initiative.** Do not silently drop the workflow-file change to make the push succeed, and do not reach for any of the resolutions below without the user explicitly authorizing that push. There is no standing authorization here — it must be granted per push.

### Sanctioned resolutions (all require explicit, per-push user authorization)

1. **User grants the scope.** They run `gh auth refresh -h github.com -s workflow` (opens a browser). It persists until they re-login, and re-running `gh auth login` sheds it. This is the durable option.

2. **Push over SSH.** SSH keys are not OAuth-scoped, so a workflow-touching push goes through. Setting the remote to SSH is usually enough — but a global `~/.gitconfig` may contain an `insteadOf` rewrite (`url.https://github.com/.insteadof git@github.com:`) that silently rewrites `git@github.com:` back to HTTPS, defeating a plain remote swap. The tell is that the rejection still names the **HTTPS** URL after you switched to SSH.

   When that rewrite is in play, force SSH for a **single** push without changing any stored config — `pushInsteadOf` takes precedence over `insteadOf` for pushes:

   ```
   git -c 'url.git@github.com:.pushInsteadOf=https://github.com/' push -u origin <branch>
   ```

   Nothing is persisted, so there is nothing to revert afterward; the remote stays HTTPS.

### Why this is not "working around a block"

The scope check exists so a human is in the loop on workflow changes. Both resolutions keep that human in the loop — the user authorizes the specific push. SSH is a different transport for an already-authorized action, not a bypass of the protection's intent. Do not generalize this to any other blocked action, and do not move the push into a script to dodge the prompt.
