// global shared state
const global = Vue.reactive({})

// helper: GET from URL as json response
function fetchJSON(url) {
  return fetch(url).then(r => r.json())
}

// returns relative route with base site prefix stripped
function curr_path(site) {
  return window.location.toString().substr(site.length);
}

// signin/signout button
const AuthButton = {
  inject: ['global'],
  data() {
    return {
      auth_link: this.get_authlink(this.$route.fullPath)
    }
  },
  watch:{
      $route(to, from){
        this.auth_link = this.get_authlink(to.fullPath)
      }
  },
  computed: {
    greeting() {
      if (this.global.auth.session != null) {
        return "Hello, " + this.global.auth.session.user_name + "!";
      } else {
        return "";
      }
    }
  },
  methods: {
    get_authlink(path) {
      const p = path != "/signout" ? path : "/";
      return "/oauth/orcid?state=" + p;
    },
    signout() {
      fetch('/oauth/signout').then(r => {
        if (r.status != 200) {
          console.log("WARNING: signout at server failed. We can still proceed.")
        }

        global.auth.session = null;
        this.$router.push('/signout')
      })
    }
  },
  template: `
<span id="auth-button" v-if="global.auth.orcid_enabled">
  {{greeting}}
  <span v-if="global.auth.session == null" id="signin-button">
    <a class="button" v-bind:href="auth_link">
      <i class="fab fa-orcid"></i>
      Sign in with ORCID
    </a>
  </span>
  <span v-else id="signout-button">
    <a class="button" v-on:click="signout()">Sign out</a>
  </span>
</span>`
}

async function init() {
  console.log("Init application...");
  arr = await Promise.all([fetchJSON('/site-base'), fetchJSON('/oauth/status')])

  global.site = arr[0];
  global.auth = arr[1];

  const authApp = Vue.createApp(AuthButton);
  authApp.use(router);
  authApp.provide('global', global);
  authApp.mount("#auth-button");
  console.log("Auth button loaded.")

  const app = Vue.createApp({})
  app.use(router)
  app.mount('#app')

  console.log("App started!")
}

window.addEventListener('DOMContentLoaded', init, false);
