/* Javascript for StaffGradedAssignmentXBlock. */
function StaffGradedAssignmentXBlock(runtime, element) {
    function xblock($, _) {
        var uploadUrl = runtime.handlerUrl(element, 'student_upload_file');
        var studentDownloadUrl = runtime.handlerUrl(element, 'student_download_file');
        var studentDownloadZippedUrl = runtime.handlerUrl(element, 'student_download_zipped')
        var submitUrl = runtime.handlerUrl(element, 'student_submit');
        var deleteSubmissionFileUrl = runtime.handlerUrl(element, 'student_delete_file')

        var staffDownloadUrl = runtime.handlerUrl(element, 'staff_download_file');
        var staffDownloadZippedUrl = runtime.handlerUrl(element, 'staff_download_zipped');

        var annotatedUploadUrl = runtime.handlerUrl(element, 'staff_upload_annotated');
        var studentAnnotationDownloadUrl = runtime.handlerUrl(element, 'student_download_annotated');
        var studentAnootationDownloadZippedUrl = runtime.handlerUrl(element, 'student_download_annotated_zipped');
        var deleteAnnotationFileUrl = runtime.handlerUrl(element, 'staff_delete_annotated');

        var staffDownloadAnnotatedUrl = runtime.handlerUrl(element, 'staff_download_annotated');
        var staffDownloadAnnotatedZippedUrl = runtime.handlerUrl(element, 'staff_download_annotated_zipped');

        var getStaffGradingUrl = runtime.handlerUrl(element, 'get_staff_grading_data');
        var enterGradeUrl = runtime.handlerUrl(element, 'staff_enter_grade');
        var removeGradeUrl = runtime.handlerUrl(element, 'staff_remove_grade');
        
        var reopenSubmissionUrl = runtime.handlerUrl(element, 'staff_reopen_submission');
        var removeSubmissionUrl = runtime.handlerUrl(element, 'staff_remove_submission')
        var reopenAllSubmissionsUrl = runtime.handlerUrl(element, 'staff_reopen_all_submissions');
        var removeAllSubmissionsUrl = runtime.handlerUrl(element, 'staff_remove_all_submissions');

        
        var template = _.template($(element).find("#sga-tmpl").text());
        var gradingTemplate;

        function render(state) {
            // Add download urls to template context
            state.downloadUrl = studentDownloadUrl;
            state.downloadZippedUrl = studentDownloadZippedUrl;
            state.downloadAnnotatedUrl = studentAnnotationDownloadUrl;
            state.downloadAnnotatedZippedUrl = studentAnootationDownloadZippedUrl;
            state.error = state.error ? state.error : false;

            // Render template
            var content = $(element).find("#sga-content").html(template(state));

            // Set up file upload
            $(content).find(".fileupload").fileupload({
                url: uploadUrl,
                add: function(e, data) {
                    var do_upload = $(content).find(".upload").html('');
                    $('<button/>')
                        .text('Upload ' + data.files[0].name)
                        .appendTo(do_upload)
                        .click(function() {
                            do_upload.text("Uploading...");
                            data.submit();
                        });
                },
                progressall: function(e, data) {
                    var percent = parseInt(data.loaded / data.total * 100, 10);
                    $(content).find(".upload").text(
                        "Uploading... " + percent + "%");
                },
                fail: function(e, data) {
                    /**
                     * Nginx and other sanely implemented servers return a 
                     * "413 Request entity too large" status code if an 
                     * upload exceeds its limit.  See the 'done' handler for
                     * the not sane way that Django handles the same thing.
                     */
                    if (data.jqXHR.status == 413) {
                        /* I guess we have no way of knowing what the limit is
                         * here, so no good way to inform the user of what the
                         * limit is.
                         */
                        state.error = "The file you are trying to upload is too large."
                    }
                    else {
                        // Suitably vague
                        state.error = "There was an error uploading your file.";

                        // Dump some information to the console to help someone
                        // debug.
                        console.log("There was an error with file upload.");
                        console.log("event: ", e);
                        console.log("data: ", data);
                    }
                    render(state);
                },
                done: function(e, data) { 
                    /* When you try to upload a file that exceeds Django's size
                     * limit for file uploads, Django helpfully returns a 200 OK
                     * response with a JSON payload of the form:
                     * 
                     *   {'success': '<error message'}
                     * 
                     * Thanks Obama!
                     */
                    if (data.result.success !== undefined) {
                        // Actually, this is an error
                        state.error = data.result.success;
                        render(state);
                    }
                    else {
                        // The happy path, no errors
                        render(data.result); 
                    }
                }
            });

            //submission file deletion
            $(content).find(".filedelete").click(function(e)
            {
                var url = deleteSubmissionFileUrl + '/' + state.uploaded[this.value].sha1;
                $.get(url).success(
                    (function (i) {
                        if (i < state.uploaded.length)
                        {
                            state.uploaded.splice(i, 1);
                        }
                    })(this.value)
                );
                render(state);
            });

            $(content).find(".assingmentsubmit").click(function(e)
            {
                $.get(submitUrl).success(function () {
                    state.submitted = true;
                    state.upload_allowed = false;
                    render(state);
                });
            });
        }

        function renderStaffGrading(data) {
            $(".grade-modal").hide();
            //$(".annotated-modal").hide();

            // Add download urls to template context
            data.downloadUrl = staffDownloadUrl;
            data.downloadZippedUrl = staffDownloadZippedUrl;
            data.reopenSubmissionUrl = reopenSubmissionUrl;
            data.removeSubmissionUrl = removeSubmissionUrl;

            // Render template
            $(element).find("#grade-info")
                .html(gradingTemplate(data))
                .data(data);

            // Map data to table rows
            data.assignments.map(function(assignment) {
                $(element).find("#grade-info #row-" + assignment.module_id)
                    .data(assignment);
            });

            // Set up grade entry modal
            $(element).find(".enter-grade-button")
                .leanModal({closeButton: "#enter-grade-cancel"})
                .on("click", handleGradeEntry);

            //set up annotated file submision modal
            $(element).find(".manage-annotated-button")
                .leanModal({closeButton: "#manage-annotated-exit"})
                .on("click", handleManageAnnotated)

            //all submission control
            $(element).find(".remove-all-submissions-button")
                .on("click", function(){
                    var url = removeAllSubmissionsUrl;
                    $.get(url).success(renderStaffGrading);
                });

            $(element).find(".reopen-all-submissions-button")
                .on("click", function(){
                    var url = reopenAllSubmissionsUrl;
                    $.get(url).success(renderStaffGrading);
                });

            //Remove a submission, including grades and files.
            $(element).find(".remove-submission-button")
                .on("click", function(){
                    var url = removeSubmissionUrl + "?module_id=" + $(this).parents("tr").data("module_id");
                    $.get(url).success(renderStaffGrading);
                });

            //reopens a submission for a student.  Clears previous grade.
            $(element).find(".reopen-submission-button")
                .on("click", function(){
                    var url = reopenSubmissionUrl + "?module_id=" + $(this).parents("tr").data("module_id");
                    $.get(url).success(renderStaffGrading);
                });

            //All upload, download and delete for annotated files
            function handleManageAnnotated() 
            {
                var row = $(this).parents("tr");
                var form = $(element).find("#manage-annotations-form");
                var uploadField = form.find(".fileuploadAnnotated");

                $(element).find("#student-name-annotations").text(row.data("fullname"));
                //var annotated = row.data("annotated");
                form.find("#fileuploadError").text("");

                populateAnnotationList();

                form.find("#annotated-download-all").attr(
                    "href", staffDownloadAnnotatedZippedUrl + "?module_id=" + row.data("module_id"));

                uploadField.fileupload({
                    url: annotatedUploadUrl + "?module_id=" + row.data("module_id"),
                    add: function(e, data) {
                        var do_upload = form.find(".uploadAnnotated").html('');
                        $('<button/>')
                            .text('Upload ' + data.files[0].name)
                            .appendTo(do_upload)
                            .click(function() {
                                do_upload.text("Uploading...");
                                data.submit();
                            });
                    },
                    progressall: function(e, data) {
                        var percent = parseInt(data.loaded / data.total * 100, 10);
                        form.find(".uploadAnnotated").text(
                            "Uploading... " + percent + "%");
                    },
                    fail: function(e, data) {
                        var error = "";
                        if (data.jqXHR.status == 413) {
                            error = "The file you are trying to upload is too large."
                        }
                        else {
                            // Suitably vague
                            error = "There was an error uploading your file.";

                            console.log("There was an error with file upload.");
                            console.log("event: ", e);
                            console.log("data: ", data);
                        }
                        form.find("#fileuploadError").text(error);
                        //display error
                        //handleManageAnnotatedInner(row);

                    },
                    done: function(e, data) { 
                        if (data.result.success !== undefined) {
                            // Actually, this is an error
                            error = data.result.success;
                            form.find("#fileuploadError").text(data.result.success);
                        }
                        else {
                            // The happy path, no errors
                            renderStaffGrading(data.result);
                            populateAnnotationList();
                        }
                        //handleManageAnnotatedInner(row);
                        //reset the upload field.
                        var uploadDiv = form.find(".uploadAnnotated").html(
                            '<input class="fileuploadAnnotated" type="file" name="annotation"/>'
                          + '<button>Select a file</button>'
                        );
                        //row.find(".manage-annotated-button").click();
                    }
                });

                form.find(".annotatedFileDelete").on("click", row, function(filelist) {
                    var url = deleteAnnotationFileUrl + "/" + row.data("annotated").sha1
                        + '?module_id=' + row.data("module_id");
                    $.get(url).success(function(data) {
                        renderStaffGrading(data);
                        populateAnnotationList();
                    });
                });

                form.find("#manage-annotated-exit").on("click", function() {
                    setTimeout(function() {
                        $("#grade-submissions-button").click(); 
                    }, 225);
                });

                //Creates the list of annotated files.
                function populateAnnotationList()
                {
                    var fileContent;

                    var annotated = row.data("annotated");
                    if (annotated.length > 0)
                    {
                        fileContent = "<table>";
                        for (var i = 0; i < annotated.length; i++)
                        {
                            fileContent += '<tr> <td>'
                                + '<a href="' + staffDownloadAnnotatedUrl + '/' + annotated[i].sha1 + "?module_id=" + row.data("module_id") + '">'
                                + annotated[i].filename + "</a>"
                                + "</td><td>"
                                + '<button class="annotatedFileDelete"'
                                +   'value="' + i + '" type="button" name="deleteannotated">'
                                +   'delete'
                                + '</button>'
                                + '</td> </tr>';
                        }
                        fileContent += "</table>";
                    }
                    else
                    {
                        fileContent = "<p>No annotations available for this student.</p>";
                    }

                    form.find("#annotated-file-list").html(fileContent);
                }
            }
        }

        /* Click event handler for "enter grade" */
        function handleGradeEntry() {
            var row = $(this).parents("tr");
            var module_id = row.data("module_id")
            var form = $(element).find("#enter-grade-form");
            $(element).find("#student-name").text(row.data("fullname"));
            form.find("#module_id-input").val(row.data("module_id"));
            form.find("#grade-input").val(row.data("score"));
            form.find("#comment-input").text(row.data("comment"));
            form.off("submit").on("submit", function(event) {
                var max_score = row.parents("#grade-info").data("max_score");
                var score = Number(form.find("#grade-input").val());
                event.preventDefault();
                if (isNaN(score)) {
                    form.find(".error").html("<br/>Grade must be a number.");
                } 
                else if (score < 0) {
                    form.find(".error").html("<br/>Grade must be positive.");
                }
                else if (score > max_score) {
                    form.find(".error").html("<br/>Maximum score is " + max_score);
                }
                else {
                    // No errors
                    $.post(enterGradeUrl, form.serialize())
                        .success(renderStaffGrading);
                }
            });
            form.find("#remove-grade").on("click", function() {
                var url = removeGradeUrl + "?module_id=" + module_id;
                $.get(url).success(renderStaffGrading);
            });
            form.find("#enter-grade-cancel").on("click", function() {
                /* We're kind of stretching the limits of leanModal, here,
                 * by nesting modals one on top of the other.  One side effect
                 * is that when the enter grade modal is closed, it hides
                 * the overlay for itself and for the staff grading modal,
                 * so the overlay is no longer present to click on to close
                 * the staff grading modal.  Since leanModal uses a fade out
                 * time of 200ms to hide the overlay, our work around is to 
                 * wait 225ms and then just "click" the 'Grade Submissions'
                 * button again.  It would also probably be pretty 
                 * straightforward to submit a patch to leanModal so that it
                 * would work properly with nested modals.
                 *
                 * See: https://github.com/mitodl/edx-sga/issues/13
                 */
                setTimeout(function() {
                    $("#grade-submissions-button").click(); 
                }, 225);
            });
        }

        //All upload, download and delete for annotated files
        function handleManageAnnotated() 
        {
            var row = $(this).parents("tr");
            var form = $(element).find("#manage-annotations-form");
            
            $(element).find("#student-name-annotations").text(row.data("fullname"));
            var annotated = row.data("annotated");
            form.find("#fileuploadError").text("");

            var annotated = row.data('annotated');

            populateAnnotationList();

            form.find("#annotated-download-all").attr(
                "href", staffDownloadAnnotatedZippedUrl + "?module_id=" + row.data("module_id"));

            form.find(".fileuploadAnnotated").fileupload({
                url: annotatedUploadUrl + "?module_id=" + row.data("module_id"),
                add: function(e, data) {
                    var do_upload = form.find(".uploadAnnotated").html('');
                    $('<button/>')
                        .text('Upload ' + data.files[0].name)
                        .appendTo(do_upload)
                        .click(function() {
                            do_upload.text("Uploading...");
                            data.submit();
                        });
                },
                progressall: function(e, data) {
                    var percent = parseInt(data.loaded / data.total * 100, 10);
                    form.find(".uploadAnnotated").text(
                        "Uploading... " + percent + "%");
                },
                fail: function(e, data) {
                    var error = "";
                    if (data.jqXHR.status == 413) {
                        error = "The file you are trying to upload is too large."
                    }
                    else {
                        // Suitably vague
                        error = "There was an error uploading your file.";

                        console.log("There was an error with file upload.");
                        console.log("event: ", e);
                        console.log("data: ", data);
                    }
                    form.find("#fileuploadError").text(error);
                    //display error
                    //handleManageAnnotatedInner(row);

                },
                done: function(e, data) { 
                    if (data.result.success !== undefined) {
                        // Actually, this is an error
                        error = data.result.success;
                        form.find("#fileuploadError").text(data.result.success);
                    }
                    else {
                        // The happy path, no errors
                        renderStaffGrading(data.result);
                        annotated = data.annotated;
                        populateAnnotationList();
                    }
                    //handleManageAnnotatedInner(row);
                }
            });

            form.find(".annotatedFileDelete").on("click", annotated, function(filelist) {
                var url = deleteAnnotationFileUrl + "/" + annotated[this.value].sha1
                    + '?module_id=' + row.data("module_id");
                $.get(url).success(function(data) {
                    renderStaffGrading(data);
                    annotated = data.annotated;
                    populateAnnotationList();
                });
                //handleManageAnnotatedInner(row);
            });

            form.find("#manage-annotated-exit").on("click", function() {
                setTimeout(function() {
                    $("#grade-submissions-button").click(); 
                }, 225);
            });

            //Creates the list of annotated files.
            function populateAnnotationList()
            {
                var fileContent;
                if (annotated.length > 0)
                {
                    fileContent = "<table>";
                    for (var i = 0; i < annotated.length; i++)
                    {
                        fileContent += '<tr> <td>'
                            + '<a href="' + staffDownloadAnnotatedUrl + '/' + annotated[i].sha1 + "?module_id=" + row.data("module_id") + '">'
                            + annotated[i].filename + "</a>"
                            + "</td><td>"
                            + '<button class="annotatedFileDelete"'
                            +   'value="' + i + '" type="button" name="deleteannotated">'
                            +   'delete'
                            + '</button>'
                            + '</td> </tr>';
                    }
                    fileContent += "</table>";
                }
                else
                {
                    fileContent = "<p>No annotations available for this student.</p>";
                }

                form.find("#annotated-file-list").html(fileContent);
            }
        }

        $(function($) { // onLoad
            var block = $(element).find(".sga-block");
            var state = block.attr("data-state");
            render(JSON.parse(state));

            var is_staff = block.attr("data-staff") == "True";
            if (is_staff) {
                gradingTemplate = _.template(
                    $(element).find("#sga-grading-tmpl").text());
                block.find("#grade-submissions-button")
                    .leanModal()
                    .on("click", function() {
                        $.ajax({
                            url: getStaffGradingUrl,
                            success: renderStaffGrading
                        });
                    });
                block.find("#staff-debug-info-button")
                    .leanModal();
            }
        });
    }

    if (require === undefined) { 
        /** 
         * The LMS does not use require.js (although it loads it...) and
         * does not already load jquery.fileupload.  (It looks like it uses
         * jquery.ajaxfileupload instead.  But our XBlock uses 
         * jquery.fileupload.
         */
        function loadjs(url) {
            $("<script>")
                .attr("type", "text/javascript")
                .attr("src", url)
                .appendTo(element);
        }
        loadjs("/static/js/vendor/jQuery-File-Upload/js/jquery.iframe-transport.js");
        loadjs("/static/js/vendor/jQuery-File-Upload/js/jquery.fileupload.js");
        xblock($, _);
    }
    else {
        /**
         * Studio, on the other hand, uses require.js and already knows about
         * jquery.fileupload.
         */
        require(["jquery", "underscore", "jquery.fileupload"], xblock);
    }
}
