function with_auth_info(f) {
  return fetch('/oauth/status')
    .then(response => response.json())
    .then(f);
}

