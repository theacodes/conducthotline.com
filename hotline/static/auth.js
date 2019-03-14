(function(){
  "use strict";

  fetch('/auth/config.json')
    .then(function(response) { return response.json(); })
    .then(function(config) {
      var loggedInContainer = document.getElementById("logged-in");

      // Next url, if it's available.
      var nextUrl = loggedInContainer.dataset.nextUrl;

      // Firebase App config, needed before FirebaseUI.
      firebase.initializeApp(config);

      // We're using session cookies to persist auth state. See
      // https://firebase.google.com/docs/auth/admin/manage-cookies

      // As httpOnly cookies are to be used, do not persist any state client side.
      firebase.auth().setPersistence(firebase.auth.Auth.Persistence.NONE);

      // FirebaseUI config.
      var uiConfig = {
        callbacks: {
          signInSuccessWithAuthResult: function(authResult, redirectUrl) {
            authResult.user.getIdToken().then(function(idToken) {
              const csrfToken = Cookies.get('_csrf_token');
              return fetch('/auth/token-login', {method: 'POST', headers: {
                'Authentication': 'Bearer ' + idToken,
                'X-CSRFToken': csrfToken
              }}).then(function(response) {
                loggedInContainer.setAttribute("class", "success");
                window.location.href = nextUrl || "/";
              })
            });
          }
        },
        signInOptions: [
          // Leave the lines as is for the providers you want to offer your users.
          firebase.auth.GoogleAuthProvider.PROVIDER_ID,
          firebase.auth.GithubAuthProvider.PROVIDER_ID,
          //firebase.auth.EmailAuthProvider.PROVIDER_ID,
          //firebase.auth.PhoneAuthProvider.PROVIDER_ID
        ],
        tosUrl: '/privacy',
        // Privacy policy url/callback.
        privacyPolicyUrl: '/privacy'
      };

      // Initialize the FirebaseUI Widget using Firebase.
      var ui = new firebaseui.auth.AuthUI(firebase.auth());
      // The start method will wait until the DOM is loaded.
      ui.start('#firebaseui-auth-container', uiConfig);
    });

})();
