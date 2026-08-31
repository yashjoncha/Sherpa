# Publishing to the VS Code Marketplace

Steps 1–3 are one-time account setup. After that, publishing is one command.

Run every command below from the `extension/` folder.

---

## Step 1 — Create an Azure DevOps organization

The Marketplace uses Azure DevOps for login. There is no way around this.

1. Go to <https://dev.azure.com>
2. Sign in with a Microsoft account (make one if needed)
3. Create an organization — any name, it is never shown to users

Free. Takes about a minute.

---

## Step 2 — Create a Personal Access Token (PAT)

This is the password `vsce` uses to publish.

1. In Azure DevOps, click your **user icon** (top right)
2. Click **Personal Access Tokens**
3. Click **New Token**
4. Fill it in:

   | Field | Value |
   |---|---|
   | Name | anything, e.g. `vsce` |
   | Organization | **All accessible organizations** |
   | Expiration | up to 1 year |
   | Scopes | click **Show all scopes**, find **Marketplace**, tick **Manage** |

5. Click **Create**
6. **Copy the token now.** It is shown only once.

> Getting *Organization* or *Scopes* wrong is the most common mistake. It fails
> later with an unhelpful 401 error.

---

## Step 3 — Create your publisher

1. Go to <https://marketplace.visualstudio.com/manage/createpublisher>
2. Pick a **publisher ID** — lowercase, no spaces, unique

The ID is **permanent** and becomes half your extension's identity:

```
<publisher-id>.sherpa-tickets
```

---

## Step 4 — Add your publisher ID to `package.json`

Open `extension/package.json` and add the `publisher` line near the top:

```json
{
  "name": "sherpa-tickets",
  "displayName": "Sherpa Tickets",
  "publisher": "your-publisher-id",
  "version": "0.1.0",
```

It must match Step 3 exactly.

**This one is required.** Without it, `vsce` refuses to build with
`Missing publisher name`.

While you are in there, these two are optional but stop `vsce` from prompting:

```json
  "license": "MIT",
  "repository": {
    "type": "git",
    "url": "https://github.com/yashjoncha/Sherpa.git"
  },
```

---

## Step 5 — Write your listing page

`vsce` builds your Marketplace page from files inside `extension/`. None of
these exist yet:

| File | What it becomes |
|---|---|
| `extension/README.md` | **Your entire Marketplace page.** Missing = blank listing. |
| `extension/CHANGELOG.md` | The "Changelog" tab |
| `extension/LICENSE` | Removes a warning on every publish |

This is a **different file** from the README in the project root — `vsce` only
looks inside `extension/`.

You can skip these and `vsce` will ask "Do you want to continue? [y/N]". Your
listing will just look empty.

---

## Step 6 — Publish

```bash
cd extension
npm install
npm run compile
npx vsce login your-publisher-id     # paste the PAT from Step 2
npx vsce publish
```

Live in about 5 minutes at:

```
https://marketplace.visualstudio.com/items?itemName=your-publisher-id.sherpa-tickets
```

---

## Publishing updates later

Steps 1–5 are done forever. From now on it is just:

```bash
npx vsce publish patch    # 0.1.0 -> 0.1.1  (bug fixes)
npx vsce publish minor    # 0.1.0 -> 0.2.0  (new features)
npx vsce publish major    # 0.1.0 -> 1.0.0  (breaking changes)
```

This bumps the version in `package.json`, commits a git tag, and publishes.

The Marketplace **rejects a version number that already exists**, so always bump.
VS Code auto-updates installed copies within a day.

---

## Just building a file, without publishing

To hand someone a file to install manually:

```bash
npm run package      # creates sherpa-tickets-0.1.0.vsix
```

Install it with:

```bash
code --install-extension sherpa-tickets-0.1.0.vsix
```

No publisher account needed for this — but `package.json` still needs the
`publisher` field from Step 4.

---

## Things worth knowing before you publish

**Your server IP is public in the listing.** `sherpa.apiUrl` in `package.json`
defaults to `http://72.62.231.170:8000`. Anyone can read it in the published
listing, and every install points there by default over plain HTTP. To avoid
that, put a domain with HTTPS in front and change the default, or set it to `""`
so the extension prompts on first run.

**The ticket views return 404.** The tracker backend was removed, so
`My Tickets` and `Sprint Progress` will error for anyone who installs this
today. Only GitHub sign-in works. Worth fixing before a public listing.

---

## If something goes wrong

| Error | Fix |
|---|---|
| `Missing publisher name` | Step 4 — add `"publisher"` to `package.json` |
| `401 Unauthorized` on login | Step 2 — PAT needs **All accessible organizations** + **Marketplace: Manage** |
| `Extension version already exists` | Bump the version: `npx vsce publish patch` |
| `ENOENT: out/extension.js` | Run `npm run compile` first |
| PAT stopped working | They expire — make a new one and `npx vsce login` again |
| Sidebar does not appear at all | An icon in `contributes` points at a file that is not in the package. VS Code drops the view container silently. Check `media/` |
