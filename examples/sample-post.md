# Why Your Supabase RLS Policies Are Failing in Production

You added row-level security. You tested it in the studio. Every query returned exactly what you expected. Then you shipped to production and suddenly half your users are getting empty tables.

This is the most common Supabase gotcha we see, and it comes down to one thing: **the JWT role claim**.

## The gap between the studio and your app

When you test in the Supabase studio, you're running queries as the `postgres` superuser. RLS doesn't apply to superusers. So every test you ran was essentially bypassing the policies you wrote.

Your app uses the `anon` or `authenticated` role, which follows RLS rules strictly. If your policy says `auth.uid() = user_id`, and a user hits an endpoint where the JWT is missing or expired, they get nothing — no error, just an empty result set.

## The three failure modes

**1. Missing JWT in server-side calls**

If you're calling Supabase from a server function using the service role key, that's fine — the service role bypasses RLS intentionally. But if you're using the anon key in a server function, you need to pass the user's JWT manually:

```typescript
const supabase = createClient(url, anonKey, {
  global: { headers: { Authorization: `Bearer ${userJwt}` } },
});
```

Most teams forget this on their first serverless function.

**2. Expired tokens**

Supabase tokens expire after one hour by default. If your frontend isn't refreshing the session, calls made after the hour mark will fail silently. The fix is to call `supabase.auth.getSession()` before any important write operation and check that the session isn't null.

**3. Wrong column type for user_id**

Your `users` table has `id` as a UUID. Your application table has `user_id` as a `text` type. The comparison fails silently because `uuid != text`. Always use `uuid` for any column you're comparing against `auth.uid()`.

## The policy that actually works

Here's a policy structure that handles the most common case — a user can only read and write their own rows:

```sql
-- Read own rows
create policy "Users can read own data"
  on public.posts for select
  using (auth.uid() = user_id);

-- Write own rows
create policy "Users can insert own data"
  on public.posts for insert
  with check (auth.uid() = user_id);

-- Update own rows
create policy "Users can update own data"
  on public.posts for update
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);
```

The `with check` clause on updates is one people frequently miss. Without it, a user could update a row to change `user_id` to someone else's ID.

## Debugging in production

Add a test endpoint that returns the current JWT claims:

```typescript
const { data: { user } } = await supabase.auth.getUser();
console.log('Current user ID:', user?.id);
console.log('Role:', user?.role);
```

Compare that `id` against what's in your `user_id` column. If they don't match exactly, that's your bug.

For server-side debugging, log the raw JWT and decode it at jwt.io to check the `sub` claim. That `sub` value is what `auth.uid()` returns in your policies.

## The broader lesson

RLS works. The policies aren't the problem — the assumptions about what role is making the request usually are. Before assuming your policy is wrong, verify the JWT is present, valid, and being sent with the request.

Once you internalize that distinction between the studio's superuser context and your app's authenticated context, RLS debugging becomes straightforward.
