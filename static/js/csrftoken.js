// AJAX请求，获取csrftoken
$.ajaxSetup({
    beforeSend: function (xhr, settings) {
        function getCookie(name) {
            let cookieValue = null;
            if (document.cookie && document.cookie !== '') {
                const cookies = document.cookie.split(';');
                for (let i = 0; i < cookies.length; i++) {
                    const cookie = jQuery.trim(cookies[i]);
                    // Does this cookie string begin with the name we want?
                    if (cookie.substring(0, name.length + 1) === (`${name}=`)) {
                        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                        break;
                    }
                }
            }
            return cookieValue;
        }

        function csrfSafeMethod(method) {
            // these HTTP methods do not require CSRF protection
            return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
        }

        if (!csrfSafeMethod(settings.type) && !this.crossDomain) {
            const csrftoken = getCookie('sops-engine-svct_csrftoken');
            xhr.setRequestHeader('X-CSRFToken', csrftoken);
        }
    },
});
