<?php
/*
 * bs5plain theme for Bludit
 *
 * footer.php (bs5plain)
 * Copyright 2024 Joaquim Homrighausen; all rights reserved.
 * Development sponsored by WebbPlatsen i Sverige AB, www.webbplatsen.se
 *
 * This file is part of bs5plain. bs5plain is free software.
 *
 * bs5plain is free software: you may redistribute it and/or modify it  under
 * the terms of the GNU AFFERO GENERAL PUBLIC LICENSE v3 as published by the
 * Free Software Foundation.
 *
 * bs5plain is distributed in the hope that it will be useful, but WITHOUT
 * ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
 * FITNESS FOR A PARTICULAR PURPOSE. See the GNU AFFERO GENERAL PUBLIC LICENSE
 * v3 for more details.
 *
 * You should have received a copy of the GNU AFFERO GENERAL PUBLIC LICENSE v3
 * along with the bs5plain package. If not, write to:
 *  The Free Software Foundation, Inc.,
 *  51 Franklin Street, Fifth Floor
 *  Boston, MA  02110-1301, USA.
 */
?>
<footer class="footer mt-auto py-3 bg-body-secondary">
    <div class="container-fluid">
        <div class="container-lg d-flex justify-content-between flex-column flex-md-row align-items-center">
            <div class="flex-grow-1 text-body small">
                <?php echo $site->footer(); ?>
            </div>
            <div class="small text-body text-opacity-50">
            <?php echo $language->get( 'Powered by' ); ?> <a class="text-body text-opacity-50" href="https://www.bludit.com" title="Open Source CMS">Bludit</a>
            </div>
        </div>
    </div>
</footer>
