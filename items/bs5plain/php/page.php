<?php
defined( 'BLUDIT' ) || die( 'That did not work as expected.' );
/*
 * bs5plain theme for Bludit
 *
 * page.php (bs5plain)
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

Theme::plugins('pageBegin');

if ( ! $page->isStatic() && ! $url->notFound() && $page->type() !== 'published' && $page->type() !== 'sticky' ) {
    echo '<section class="mt-5 mb-5 p-5">' .
         '<container>' .
         '<div class="h3 mt-5 text-center">' .
         $language->get( 'This post is not available at the moment' ) .
         '</div></container>'.
         '</section>';
    Theme::plugins('pageEnd');
    exit;
}
?>
<section class="pt-5 pt-lg-1 mt-5 mt-lg-1 mb-4">
    <div class="container">
        <div class="row">
            <div class="col-lg-8 mx-auto shadow mb-5 bg-body p-3 rounded-2">
                <div class="bs5plain-page-header">
                    <?php
                    // Title
                    if ( ! $url->notFound() ) {
                        echo '<h1 class="h4 fw-medium">' . $page->title() . '</h1>';
                        // Post time
                        if ( ! $page->isStatic() ) {
                            $reading_time = trim( $page->readingTime() );
                            // $post_time = date_create_immutable( $page->dateRaw() );
                            $post_time = date_create_immutable( $page->dateRaw() );
                            if ( $post_time ) {
                                echo '<div class="small text-secondary">' .
                                     '<span class="me-2">' . '&#x1F4C5;' . '</span>' .
                                     '<span class="font-monospace">' .
                                     $post_time->format( $site->db['dateFormat'] ) .
                                     ', ' .
                                     $reading_time .
                                     '</span></div>';
                            }
                        }
                    }
                    // Description
                    /*
                    if ( $page->description() ) {
                        echo '<div class="h6 my-2 text-body-secondary"><em>' . $page->description() . '</em></div>';
                    }
                    */
                    // Sub pages
                    if ( $page->hasChildren() ) {
                        $children = $page->children();
                        if ( count( $children ) < 4 ) {
                            // We show up to three children inline
                            echo '<div class="bg-body-secondary rounded-3 p-2 mb-2">';
                            echo '<div class="small ms-1 p-1">';
                            echo '<span class="badge text-bg-primary">' . $language->get( 'Child pages' ) . '</span>';
                            echo '</div>';
                            echo '<ul class="ms-3 p-1">';
                            foreach( $children as $child ) {
                                echo '<li class="text-truncate small">' .
                                     '&raquo;&nbsp;' .
                                     '<a class="link-body-emphasis link-opacity-75 link-offset-2 link-underline-opacity-25 link-underline-opacity-100-hover" href="' . $child->permaLink() . '" title="' . $child->title() . '">' .
                                     $child->title() .
                                     '</a>';
                            }
                            echo '</ul>';
                            echo '</div>';
                        } else {
                            // We show >3 children as a dropdown
                            echo '<button class="btn btn-secondary btn-sm dropdown-toggle" type="button" data-bs-toggle="collapse" data-bs-target="#collapseChildren" aria-expanded="false" aria-controls="collapseChildren">' .
                                 $language->get( 'Child pages' ) . '&nbsp;' .
                                 '</button>';
                            echo '<div class="bg-body-secondary rounded-3 p-2 collapse mt-2" id="collapseChildren">';
                            echo '<ul class="p-0 m-0">';
                            foreach( $children as $child ) {
                                echo '<li class="text-truncate small">' .
                                     '&raquo;&nbsp;' .
                                     '<a class="link-body-emphasis link-opacity-75 link-offset-2 link-underline-opacity-25 link-underline-opacity-100-hover" href="' . $child->permaLink() . '" title="' . $child->title() . '">' .
                                     $child->title() .
                                     '</a>' .
                                     '</li>';
                            }
                            echo '</ul>';
                            echo '</div>';
                        }
                    } elseif ( $page->isChild() ) {
                        echo '<div class="bg-body-secondary rounded-3 p-3 mt-2 small text-truncate">';
                        echo '&raquo;&nbsp;' .
                             '<a class="link-offset-2 link-underline-opacity-25 link-underline-opacity-100-hover" href="' . $page->parentMethod( 'permaLink' ) .
                             '" title="' . $language->get( 'Parent page' ) . ': ' . $page->parentMethod( 'title' ) . '">' .
                              $page->parentMethod( 'title' ) .
                              '</a>';
                        echo '</div>';
                    }
                    // Cover image
                    if ( $page->coverImage() ) {
                        echo '<div class="text-center">';
                        echo '<img class="img-thumbnail bs5plain-cover-img p-2" src="' . $page->coverImage() . '" />';
                        echo '</div>';
                    }
                    echo '</div>';// bs5plain-page-header
                    // Content
                    echo '<div class="bs5plain-page-content mt-3">' .
                         $page->content() .
                         '</div>';
                    // Check tags
                    $post_tags = $page->tags( true );
                    if ( ! empty( $post_tags ) ) {
                        echo '<div class="bsplain-page-content-tags small">';
                        foreach( $post_tags as $tag_key => $tag_name ) {
                            echo '<a class="badge text-bg-secondary text-decoration-none me-2" href="' .
                                 DOMAIN_TAGS . $tag_key . '">' .
                                 $tag_name .
                                 '</a>';
                        }
                        echo '</div>';
                    }
                    ?>
            </div>
        </div>
    </div>
</section>

<?php Theme::plugins('pageEnd'); ?>
