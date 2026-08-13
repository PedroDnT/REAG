# Deploying the dashboard

`scripts/build_dashboard.py` emits one self-contained HTML file. There is no
build step, no server, and no runtime dependency — any static host will serve it.

## Build

```bash
python scripts/build_dashboard.py \
    --run    reports/investigation/<run_id> \
    --output public/index.html
```

## Deploy to Vercel

```bash
npx vercel deploy --prod public/
```

`public/vercel.json` sets the cache headers; Vercel needs no other configuration
because there is nothing to build.

## A note on size

Page weight scales with the fund universe, and almost all of it is the fund
table:

| Scope | Funds | Page |
|---|---:|---:|
| One administrator or manager | ~100 | ~60 KB |
| A full CVM month | 25,509 | ~1.5 MB without names, ~3 MB with |

The payload is already encoded columnar — funds are tuples against a shared test
index rather than objects repeating their keys 25,509 times, which is roughly a
7× saving over the naive form. What remains is irreducible: the fund names are
most of it, and they are what makes search by name work.

Three megabytes is unremarkable for a static host and loads fine over a normal
connection. It is only a problem for tooling that has to carry the file contents
inline — which is why a full-universe page is deployed with the command above
rather than through an assistant's deploy tool.

**Do not trim the universe to shrink the page.** A fund missing from the table
cannot be distinguished from a fund that was checked and came back clean, and
that conflation is the one thing this page exists to prevent. Trim names before
you trim rows; search by CNPJ still works without them.
