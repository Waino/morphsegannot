var app = {
    tag_types: ['PRE', 'STM', 'SUF'],
    /* Be careful with caps, whitespace and punctuation */
    ui_string: {
        'lang': 'saamenkielen',
        'email': 'sähköposti',
        'login': 'Kirjaudu sisään',
        'removeall': 'Poista morfirajat',
        'unskip': 'Takaisin yli hypättyihin sanoihin',
        'skip': 'Hyppää tämän sanan yli',
        'submit_seg': 'Hyväksy segmentaatio',
        'back_seg': 'Takaisin segmentaatioon',
        'submit_tags': 'Hyväksy tagit',
        'skipped': 'Yli hypätyt',
        'skipped_expl': 'Kysyy uudelleen yli hypätyt sanat.',
        'first_set': '1. joukko',
        'second_set': '2. joukko',
        'of_eval': ' evaluaatiosanoja',
        'no_pred': 'Sanoille ei ehdoteta segmentaatiota.',
        'train': 'Opetussanoja',
        'pred': 'Nykyisen mallin segmentaatio annetaan ehdotuksena.',
        'extra_words': ' Nämä ovat "extra" evaluaatiosanoja, ' +
                       'joiden avulla saadaan tarkempia tuloksia. ' +
                       'Voit lopettaa annotoinnin kun väsyt.',
        'iter_done': 'Iteraatio on päättynyt',
        'thanks': 'Kiitos avustasi!',
        'next_phase': 'Seuraava vaihe: ',
        'cur_iter': 'Iteraatio: ',
        'cur_phase': 'Vaihe: ',
        'c_annot': 'Annotoitu: ',
        'c_skip': ', ylihypätty: ',
        'c_rem': ', jäljellä: ',
        'sense': 'Eri paradigma',
        'tag_all': 'Valitse tagi jokaiselle morfille',
        'illegal': 'Prefiksiä (PRE) ei voi välittömästi seurata suffiksi (SUF).'
    },
    initialize: function(container, status_container) {
        /* UI strings containing other UI strings need to be set here */
        app.ui_string['nonword'] = 'Tämä ei ole ' + app.ui_string['lang'] + ' sana',
        app.container = container;
        app.status_container = status_container;
        app.control_containers = [];
        app.add_login(container);
        app.add_status(status_container);
        app.prev_phase = false;
    },
    add_login: function(container) {
        input = $('<input id="email" type="email" name="email" autofocus="true"></input>');
        input.attr('placeholder', app.ui_string['email']);
        input.on('keypress', function(e) {
            if(e.which == 13) { app.do_login(); }
        });
        button = $('<button></button>');
        button.text(app.ui_string['login']);
        button.on('click', app.do_login);
        app.container.append(input);
        app.container.append(button);
    },
    add_status: function(container) {
        container.append($('<span id="leftstatus" class="statusbox"></span>'));
        container.append($('<span id="rightstatus" class="statusbox"></span>'));
    },
    do_login: function() {
        email = $('#email').val();
        $.getJSON('/user/' + email, {'width': window.screen.width},
            function(data) {
                app.uid = data['uid'];
                app.completed = data['annotated'];
                app.iteration = data['iteration'];
                app.container.empty();
                app.show_controls('one');
                $.getJSON('/words/' + app.uid, function(data) {
                    app.words = data['words']
                    app.skipped = [];
                    app.un_skipped = false;
                    app.other_senses = [];
                    app.next_word();
                });
            });
    },
    add_controls: function(container) {
        container.addClass('hidden');
        
        pane1 = $('<div class="pane_one"></div>');
        unskipbutton = $('<button class="unskip hidden"></button>');
        unskipbutton.text(app.ui_string['unskip']);
        unskipbutton.on('click', app.unskip);
        pane1.append(unskipbutton);
        resetbutton = $('<button></button>');
        resetbutton.text(app.ui_string['removeall']);
        resetbutton.on('click', app.reset);
        pane1.append(resetbutton);
        noisebutton = $('<button></button>');
        noisebutton.text(app.ui_string['nonword']);
        noisebutton.on('click', app.noise);
        pane1.append(noisebutton);
        skipbutton = $('<button class="skip"></button>');
        skipbutton.text(app.ui_string['skip']);
        skipbutton.on('click', app.skip);
        pane1.append(skipbutton);
        submitbutton = $('<button class="submit_seg submit"></button>');
        submitbutton.text(app.ui_string['submit_seg']);
        submitbutton.on('click', app.submit_seg);
        pane1.append(submitbutton);

        pane2 = $('<div class="pane_two"></div>');
        backbutton = $('<button></button>');
        backbutton.text(app.ui_string['back_seg']);
        backbutton.on('click', function() { app.show_data('one'); });
        pane2.append(backbutton);
        submitbutton = $('<button class="submit_tags submit" disabled="true"></button>');
        submitbutton.text(app.ui_string['submit_tags']);
        submitbutton.on('click', app.submit);
        pane2.append(submitbutton);

        container.append(pane1);
        container.append(pane2);
        app.control_containers[app.control_containers.length] = container;
    },
    update_counts: function() {
        if(app.un_skipped && app.skipped.length > 0) {
            $('button.skip').attr('disabled', 'true');
            $('button.unskip').attr('disabled', 'true');
        } else {
            app.un_skipped = false;
            $('button.skip').removeAttr('disabled');
            $('button.unskip').removeAttr('disabled');
        }
        if(app.un_skipped) {
            phase = app.ui_string['skipped'];
            expl = app.ui_string['skipped_expl'];
        } else if (app.words.length > 0) {
            phase = app.words[0][0];
            if(app.words[0][1]) {
                expl = app.ui_string['pred'];
            } else {
                expl = app.ui_string['no_pred'];
            }
        } else {
            phase = app.ui_string['iter_done'];
            expl = app.ui_string['thanks'];
        }

        if(phase != app.prev_phase) {
            alert(app.ui_string['next_phase'] + phase + '\n\n' + expl);
        }
        app.prev_phase = phase;

        $('#rightstatus').empty();
        toprow = $('<div></div>');
        bottomrow = $('<div></div>');
        toprow.text(
            app.ui_string['cur_iter'] + app.iteration + '.' +
            app.ui_string['cur_phase'] + phase + '.');
        counttxt = 
            app.ui_string['c_annot'] + app.completed +
            app.ui_string['c_skip'] + app.skipped.length +
            app.ui_string['c_rem'];
        for(i=0; i<app.words.length; i++) {
            if(i > 0) {
                counttxt = counttxt + ' + ';
            }
            counttxt = counttxt + app.words[i][2].length;
        }
        bottomrow.text(counttxt);
        $('#rightstatus').append(toprow).append(bottomrow);
    },
    next_word: function() {
        if(app.other_senses.length > 0) {
            app.reshow_other_senses();
            return;
        }
        if(app.un_skipped && app.skipped.length > 0) {
            buffer = app.skipped;
        } else if(app.words.length > 0) {
            while(app.words[0][2].length == 0) {
                app.words.shift();
            }
            buffer = app.words[0][2];
        } else {
            app.done();
            return;
        }
        app.update_counts();
        word = buffer.shift();

        app.show_data('one');
        $.getJSON('/word/' + word, {'uid': app.uid}, app.set_word).fail(function() {
            alert('Error in retrieving the next word to annotate');
        });
    },
    set_word: function(data) {
        app.set_type(data['word'], data['boundaries']);
        nobutton = (data['contexts'].length == 1);
        $.each(data['contexts'], function(i, pair) {
            app.add_context(pair[0], pair[1], pair[2], nobutton)
        });
    },
    empty_container: function() {
        app.container.empty();
        app.container.append($('<div class="pane data_one"></div>'));
        app.container.append($('<div class="pane data_two suppressed"></div>'));
    },
    set_type: function(word, splits) {
        app.word_type = word;
        app.empty_container();
        if(word.length != splits.length + 1) {
            throw 'Invalid split vector length ' + word.length + ' + ' + splits.length;
        }
        app.splits = splits;
        app.contexts = {};
    },
    add_context: function(lcontext, rcontext, id, nobutton) {
        app.contexts[id] = true;
        row = $('<div class="row">' +
                '<div class="entry"><span class="lcontext"></span>' +
                                   '<span class="token"></span>' +
                                   '<span class="rcontext"></span></div>' +
                                   '<button></button>' +
                '</div>');
        row.find('.lcontext').text(lcontext);
        row.find('.rcontext').text(rcontext);
        if(nobutton) {
            row.find('button').remove();
        } else {
            row.find('button').on('click', app.remove_context)
                            .attr('id', id)
                            .text(app.ui_string['sense']);
        }

        tokenspan = row.find('.token');
        $.each(app.word_type.split(''), function(i, letter) {
            letterspan = $('<span class="letter"></span>');
            letterspan.data('letterindex', i);
            if(i < app.word_type.length - 1) {
                if(app.splits[i]) {
                    letterspan.addClass('split');
                } else {
                    letterspan.addClass('unsplit');
                }
                letterspan.on('click', app.click_at);
            }
            letterspan.text(letter);
            tokenspan.append(letterspan);
        });
        app.container.find('.data_one').append(row);
    },
    remove_context: function() {
        rowid = $(this).attr('id');
        rowspan = $('#' + rowid).parent()
        lcontext = rowspan.find('.lcontext').text();
        rcontext = rowspan.find('.rcontext').text();
        rowspan.remove();
        app.contexts[rowid] = false;
        $.post('/sense/' + rowid, {'uid': app.uid});

        oss = app.other_senses;
        oss[oss.length] = [lcontext, rcontext, rowid];
    },
    reshow_other_senses: function() {
        app.empty_container();
        app.show_data('one');
        app.contexts = {};
        nobutton = (app.other_senses.length == 1);
        $.each(app.other_senses, function(i, row) {
            app.add_context(row[0], row[1], row[2], nobutton);
        });
        app.other_senses = [];
    },
    check_tags: function() {
        checked = app.container.find('input:checked')
        $.each(checked, function(i, x) {
            morph = $(x).parents('.morph');
            morph.removeClass('PRE');
            morph.removeClass('STM');
            morph.removeClass('SUF');
            morph.addClass($(x).attr('value'));
        });
        if(checked.length < app.num_morphs) {
            $('#leftstatus').text(app.ui_string['tag_all'])
                            .removeClass('illegal');
            app.tag_sequence = false;
            $('.submit_tags').attr('disabled', 'true');
            return;
        }
        tags = [];
        prev = false;
        cur = false;
        illegal = false;
        $.each(checked, function(i, x) {
            prev = cur;
            cur = $(x).attr('value');
            tags[tags.length] = cur;
            if(cur == 'SUF' && prev == 'PRE') {
                /* illegal, disable and warn */
                illegal = true;
            }
        });
        if(illegal) {
            $('#leftstatus').text(app.ui_string['illegal'])
                            .addClass('illegal');
            $('.submit_tags').attr('disabled', 'true');
            app.tag_sequence = false;
            return;
        }
        app.tag_sequence = tags;
        $('#leftstatus').text('')
                        .removeClass('illegal');
        $('.submit_tags').removeAttr('disabled');
    },
    elicit_tags: function(data) {
        app.container.find('.data_two').empty();
        app.show_data('two');
        app.num_morphs = data['segmented'].length
        if(app.num_morphs == 1) {
            /* No need to elicit tags for single-morph word */
            app.tag_sequence = ['STM'];
            app.submit();
            return;
        }
        $.each(data['segmented'], function(i, segment) {
            morphspan = $('<span class="morph">' +
                          '</span>');
            morphspan.text(segment);
            tagwrapper = $('<span class="tags"></span>');
            morphspan.append(tagwrapper);
            $.each(app.tag_types, function(j, tag_type) {
                tag = $('<span class="tag"><input type="radio"></input>' +
                        '<label></label></span>');
                tag.find('input').attr('id', tag_type + i)
                                 .attr('name', i)
                                 .attr('value', tag_type);
                tag.find('label').attr('for', tag_type + i)
                                 .text(tag_type);
                /* STM default for faster tagging */
                if(tag_type == 'STM') {
                    tag.find('input').attr('checked', 'true');
                }
                tagwrapper.append(tag);
            });
            if(i == 0) {
                morphspan.find('#SUF0').attr('disabled', 'true');
            }
            if(i == app.num_morphs - 1) {
                morphspan.find('#PRE' + i).attr('disabled', 'true');
            }
            morphspan.on('click', app.check_tags);
            app.container.find('.data_two').append(morphspan);
        });
        app.check_tags();
    },
    reset: function() {
        $.each(app.splits, function(i, val) {
            if(val) {
                app.toggle_at(i);
            }
        });
        $.post('/log/reset', {'uid': app.uid, 'message': app.word_type});
    },
    click_at: function() {
        letterindex = $.data(this, 'letterindex');
        app.toggle_at(letterindex);
        $.post('/log/click', {'uid': app.uid, 'message': letterindex});
    },
    toggle_at: function(letterindex) {
        app.container.find('.token').each(function(i, tokenspan) {
            letterspan = $($(tokenspan).children()[letterindex]);
            letterspan.toggleClass('unsplit');
            letterspan.toggleClass('split');
        });
        app.splits[letterindex] = !app.splits[letterindex];
    },
    noise: function() {
        $.post('/nonword/' + app.word_type, {'uid': app.uid});
        app.next_word();
    },
    skip: function() {
        $.post('/skip/' + app.word_type, {'uid': app.uid});
        app.skipped[app.skipped.length] = app.word_type;
        $('button.unskip').removeClass('hidden');
        app.next_word();
    },
    unskip: function() {
        app.un_skipped = true;
        app.next_word();
    },
    submit_seg: function() {
        $.post('/b2seg/' + app.word_type,
               {'uid': app.uid,
                'boundaries': JSON.stringify(app.splits),
                'contexts': JSON.stringify(app.contexts)},
               app.elicit_tags);
    },
    submit: function() {
        $.post('/word/' + app.word_type,
               {'uid': app.uid,
                'boundaries': JSON.stringify(app.splits),
                'tags': JSON.stringify(app.tag_sequence),
                'contexts': JSON.stringify(app.contexts)});
        app.completed++;
        app.next_word();
    },
    done: function() {
        app.container.empty();
        app.container.append(
            $('<span>That was all for this iteration. Thank you!</span>'));
        /* FIXME resetting skipped words, if any */
    },
    hide_controls: function() {
        $.each(app.control_containers, function(i, container) {
            container.addClass('hidden');
            container.find('div').addClass('suppressed');
        });
    },
    show_data: function(pane) {
        app.container.removeClass('hidden');
        app.container.find('.pane').addClass('suppressed');
        app.container.find('.data_' + pane).removeClass('suppressed');
        app.show_controls(pane);
        $('#leftstatus').text('')
                        .removeClass('illegal');
    },
    show_controls: function(pane) {
        $.each(app.control_containers, function(i, container) {
            container.removeClass('hidden');
            container.find('div').addClass('suppressed');
            container.find('.pane_' + pane).removeClass('suppressed');
        });
    }
};
