# Social login setup (Google, LinkedIn, GitHub)

The code is in place; each provider needs switching on once. Allow about an hour in total.
Provider websites rename their menus from time to time, so if a label below doesn't match
exactly, look for the nearest equivalent.

## The one URL every provider needs

Supabase gives you a **Callback URL**. Find it in Supabase → **Authentication → Sign In / Providers**
→ open any provider (e.g. Google). It looks like:

    https://<your-project-ref>.supabase.co/auth/v1/callback

Copy it. You'll paste it into Google, LinkedIn and GitHub below.

## 1. Supabase: allow the app to receive people back

Supabase → **Authentication → URL Configuration**

- **Site URL:** `https://crescopus.onrender.com` (change to `https://crescopus.com` once Cloudflare is live)
- **Redirect URLs** — add all of these:
  - `https://crescopus.onrender.com/auth/callback`
  - `http://127.0.0.1:5000/auth/callback` (for testing locally)
  - `http://localhost:5000/auth/callback`
  - later: `https://crescopus.com/auth/callback`

If a sign-in ends on the Supabase site instead of Crescopus, this list is the first thing to check.

## 2. Google

1. Go to **console.cloud.google.com** and create a project called *Crescopus*.
2. Open **Google Auth Platform** (formerly "OAuth consent screen"):
   - **Branding:** app name *Crescopus*, your support email, logo optional,
     app home page `https://crescopus.onrender.com`.
   - **Audience:** *External*. While it says *Testing*, only test users you add can sign in;
     press **Publish app** when you're ready for everyone. Basic name/email/photo sign-in
     doesn't need Google's verification review.
   - **Data access:** the default `openid`, `email` and `profile` are all that's needed.
3. **Clients → Create client → Web application**, name *Crescopus*.
   - **Authorised redirect URIs:** paste the Supabase Callback URL.
4. Copy the **Client ID** and **Client secret**.
5. Supabase → **Authentication → Sign In / Providers → Google**: switch on, paste both, **Save**.

## 3. LinkedIn

LinkedIn requires a **LinkedIn Company Page** to attach the app to. If Crescopus doesn't have one,
create it first (LinkedIn → *For Business* → *Create a Company Page*). It can be minimal.

1. Go to **linkedin.com/developers** → **Create app**: name *Crescopus*, choose the Company Page,
   add the logo, accept the terms.
2. **Products** tab → request **Sign In with LinkedIn using OpenID Connect**. It's usually
   approved instantly.
3. **Auth** tab → **Authorized redirect URLs for your app** → add the Supabase Callback URL.
4. Copy the **Client ID** and **Primary Client Secret** from the Auth tab.
5. Supabase → **Sign In / Providers → LinkedIn (OIDC)**: switch on, paste both, **Save**.
   (Use *LinkedIn (OIDC)*, not the older LinkedIn option.)

## 4. GitHub

1. Go to **github.com/settings/developers** → **OAuth Apps** → **New OAuth App**.
   - **Application name:** Crescopus
   - **Homepage URL:** `https://crescopus.onrender.com`
   - **Authorization callback URL:** paste the Supabase Callback URL.
2. **Register application**, then **Generate a new client secret**. Copy it straight away
   (GitHub only shows it once) along with the **Client ID**.
3. Supabase → **Sign In / Providers → GitHub**: switch on, paste both, **Save**.

## 5. Try it

Nothing new is needed in Render or `.env`.

1. Log out, open **Log in**, press **Continue with Google**.
2. With a new account you'll see **Finish setting up** (Builder or Grower, country, optional photo).
3. With an email that already has a Crescopus account, you go straight to your Home:
   Supabase links the two automatically when the email is verified.
4. Repeat for LinkedIn and GitHub.

## How it behaves

- **New people** choose Builder or Grower once, on *Finish setting up*. Until they do, they
  can't reach the rest of the app and see no menu. The role can't be changed afterwards.
- **Photo:** if the provider has one and the person has no photo yet, they're offered it
  (ticked by default, easy to untick). It's copied into Crescopus's own storage, because
  LinkedIn's photo links expire.
- **Cancelling** on the provider's page brings them back to Log in with a short message.
- If a provider isn't switched on in Supabase yet, its button shows an error from Supabase,
  so set all three up before publicising the buttons (or ask for any to be hidden for now).
