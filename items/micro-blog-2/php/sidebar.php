
<div id="nav" class="pure-u">
        <a href="#" id="menuLink" class="nav-menu-button">Menu</a>

        <div class="nav-inner">
            

            <div class="pure-menu">
                <ul class="pure-menu-list">
                    <li class="pure-menu-heading"><a href="<?php echo $site->url() ?>">
        <?php echo $site->title() ?></a></li>
        <?php
		foreach ($staticContent as $staticPage) {
			echo '<li class="pure-menu-item">';
			echo '<a class="pure-menu-link" href="'.$staticPage->permalink().'">';
			echo $staticPage->title();
			echo '</a>';
			echo '</li>';
		}
	?>
                    <?php
        if (Paginator::showPrev()) {
                echo '<li class="pure-menu-item">';
                echo '<a class="pure-menu-link" href="'.Paginator::previousPageUrl().'">'.$L->get('Previous page').'</a>';
                echo '</li>';
        }

        if (Paginator::showNext()) {
                echo '<li class="pure-menu-item">';
                echo '<a class="pure-menu-link" href="'.Paginator::nextPageUrl().'">'.$L->get('Next page').'</a>';
                echo '</li>';
        }
?>
                    
                    
                </ul>
            </div>
        </div>
    </div>