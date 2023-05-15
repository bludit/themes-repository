



<div id="list" class="pure-u-1">
        <?php foreach ($content as $page): ?>
        <div class="email-item email-item-selected pure-g">
            <div class="pure-u">
                <img width="64" height="64" alt="Tilo Mitra&#x27;s avatar" class="email-avatar" src="<?php echo ($page->user('profilePicture')?$page->user('profilePicture'):Theme::src('img/yahoo.png')) ?>">
            </div>
<?php if($page->title()): ?>
            <div class="pure-u-3-4">
                <h5 class="email-name"><?php echo $page->user('nickname'); ?>&nbsp;-&nbsp;<?php echo $page->date(); ?></h5>
                <h4 class="email-subject"><?php echo $page->title() ?></h4><?php endif ?>
                <p class="email-desc">
                    <?php echo $page->content() ?>
                </p>
                <?php if ($page->coverImage()): ?>
                        <img src="<?php echo $page->coverImage() ?>" alt="<?php echo $page->slug() ?>">
                        <?php endif ?>
            </div>
        </div>

        <?php endforeach ?>
        </div>
    </div>
