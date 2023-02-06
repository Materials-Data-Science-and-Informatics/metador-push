# Metador Push Frontend

The Metador Push frontend is implemented in [Svelte](https://svelte.dev)
and is based on [this](https://github.com/sveltejs/template) template.

The most heavy lifting is done by Uppy, JSONEditor and react-jsonschema-form, which are
wired up to provide a good user experience in a unified interface.

Run `npm install` to install all dependencies and run `npm run dev`
to run the frontend development server. It is only used for auto-reloading, not to
actually serve the page, so you also need to run the backend (see the main README file).

As a starting point, the root component of the frontend is in `src/App.svelte`.

`AuthButton` manages the authentication state and provides sign-in/sign-out.
The rest of the application mostly assumes that the user is signed in.
