<!doctype html>
<html lang="<?php echo Theme::lang() ?>">
<head>
<?php include(THEME_DIR_PHP.'head.php') ?>
</head>
<body>

<div id="layout" class="content pure-g">
    <?php include(THEME_DIR_PHP.'sidebar.php') ?>

    <?php include(THEME_DIR_PHP.'home.php') ?>
</div>
<!-- Script to make the Menu link work -->
<!-- Just stripped down version of the js/ui.js script for the side-menu layout -->
<script>
    function getElements() {
        return {
            menu: document.getElementById('nav'),
            menuLink: document.getElementById('menuLink')
        };
    }

    function toggleClass(element, className) {
        var classes = element.className.split(/\s+/);
        var length = classes.length;
        var i = 0;

        for (; i < length; i++) {
            if (classes[i] === className) {
                classes.splice(i, 1);
                break;
            }
        }
        // The className is not found
        if (length === classes.length) {
            classes.push(className);
        }

        element.className = classes.join(' ');
    }

    function toggleMenu() {
        var active = 'active';
        var elements = getElements();

        toggleClass(elements.menu, active);
    }

    function handleEvent(e) {
        var elements = getElements();

        if (e.target.id === elements.menuLink.id) {
            toggleMenu();
            e.preventDefault();
        } else if (elements.menu.className.indexOf('active') !== -1) {
            toggleMenu();
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        document.addEventListener('click', handleEvent);
    });
</script>
</body>
</html>
