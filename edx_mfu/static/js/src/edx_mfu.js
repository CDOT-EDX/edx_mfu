/* Javascript for MultipleFileUploadXBlock. */
function MultipleFileUploadXBlock(runtime, element) 
{
    function xblock($, _) 
    {
        var uploadUrl = runtime.handlerUrl(element, 'student_upload_file');
        var studentDownloadUrl = runtime.handlerUrl(element, 'student_download_file');
        var studentDownloadZippedUrl = runtime.handlerUrl(element, 'student_download_zipped')
        var submitUrl = runtime.handlerUrl(element, 'student_submit');
        var deleteSubmissionFileUrl = runtime.handlerUrl(element, 'student_delete_file')

        var staffDownloadUrl = runtime.handlerUrl(element, 'staff_download_file');
        var staffDownloadZippedUrl = runtime.handlerUrl(element, 'staff_download_zipped');

        var annotatedUploadUrl = runtime.handlerUrl(element, 'staff_upload_annotated');
        var studentAnnotationDownloadUrl = runtime.handlerUrl(element, 'student_download_annotated');
        var studentAnnotationDownloadZippedUrl = runtime.handlerUrl(element, 'student_download_annotated_zipped');
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

        
        var template = _.template($(element).find("#mfu-tmpl").text());
        var uploadTemplate = _.template($(element).find("#mfu-upload-tmpl").text());
        var filelistTemplate = _.template($(element).find("#mfu-filelist-tmpl").text());
        var gradingTemplate;

        function render(state) 
        {
            state.error = state.error ? state.error : false;

            // Render template
            var content = $(element).find("#mfu-content").html(template(state));

            var uploadData = {
                filelist:          state.uploaded,
                uploadUrl:         uploadUrl,
                downloadZippedUrl: studentDownloadZippedUrl,
                downloadUrl: function(hash) 
                {
                    return studentDownloadUrl + '/' + hash; 
                },
                deleteUrl: function(hash) 
                {
                    return deleteSubmissionFileUrl +'/' + hash;
                },
                upload_allowed:    state.upload_allowed 
            };


            var annotatedData = {
                filelist:          state.annotated,
                downloadZippedUrl: studentAnnotationDownloadZippedUrl,
                downloadUrl: function(hash) 
                {
                    return studentDownloadUrl + '/' + hash; 
                },
                deleteUrl: function(hash) 
                {
                    return "";
                },
                upload_allowed:    false
            };

            handleUpload($('#student-upload'), uploadData);
            handleFilelist($('#student-annotated'), annotatedData);
            $("#student-view-submission-time")
                .text(Date(state.submission_time)
                    .toString('MMMM, d yyyy h:mm tt'));

            //submit assignment for marking.
            $(content).find(".assingmentsubmit").click(function(e)
            {
                $.get(submitUrl).success(function () {
                    state.submitted = true;
                    state.upload_allowed = false;
                    state.submitted_on = Date.now().toString();
                    render(state);
                });
            });
        }

        function renderStaffGrading(data) 
        {
            $(".grade-modal").hide();
            //$(".annotated-modal").hide();

            var allStudentData = data;

            // Add download urls to template context
            data.downloadUrl = staffDownloadUrl;
            data.downloadZippedUrl = staffDownloadZippedUrl;            //data.removeSubmissionUrl = removeSubmissionUrl;

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
                .on("click", handleManageAnnotated);

            //all submission control
            $(element).find(".remove-all-submissions-button")
                .on("click", function()
                {
                    var url = removeAllSubmissionsUrl;
                    
                    $.get(url).success(function() {
                        allStudentData.assignments.each(
                            removeSubmission(this)
                        );

                        renderStaffGrading(allStudentData);
                    });
                });

            //reopen all submissions for the asingment.
            $(element).find(".reopen-all-submissions-button")
                .on("click", function()
                {
                    var url = reopenAllSubmissionsUrl;
                    
                    $.get(url).success(function() {
                        allStudentData.assignments.each(function() {
                            reopenSubmission(this);
                        });

                        renderStaffGrading(allStudentData);
                    });
                });

            //Remove a submission, including grades and files.
            $(element).find(".remove-submission-button")
                .on("click", function()
                {
                    var module_id = $(this).parents("tr").data("module_id");
                    var url = removeSubmissionUrl + "?module_id=" + module_id;
                    
                    $.get(url).success(function() {
                        removeSubmission($.grep(allStudentData.assignments, function(e) {
                            return e.module_id == module_id;
                        })[0]);

                        renderStaffGrading(allStudentData);
                    });
                });

            //reopens a submission for a student.  Clears previous grade.
            $(element).find(".reopen-submission-button")
                .on("click", function()
                {
                    var module_id = $(this).parents("tr").data("module_id");
                    var url = reopenSubmissionUrl + "?module_id=" + module_id;
                    
                    $.get(url).success(function() {
                        reopenSubmission($.grep(allStudentData.assignments, function(e) {
                            return e.module_id == module_id;
                        })[0]);

                        renderStaffGrading(allStudentData);
                    });
                });

            //All upload, download and delete for annotated files
            function handleManageAnnotated() 
            {   
                var row = $(this).parents("tr");
                var module_id = row.data("module_id")

                var studentData = 
                    $.grep(allStudentData.assignments, function(e){
                        return e.module_id == module_id;
                    })[0];

                $('#student-name-annotations').text(studentData.fullname);

                //Object containing data needed for rendering file list
                //and upload button.
                var fileData = {
                    filelist:          studentData.annotated,
                    uploadUrl:         annotatedUploadUrl + "?module_id=" 
                                       + studentData.module_id,
                    downloadZippedUrl: staffDownloadAnnotatedZippedUrl 
                                       + "?module_id=" + studentData.module_id,
                    downloadUrl: function(hash) 
                    {
                        return staffDownloadAnnotatedUrl + '/' + hash 
                        + "?module_id=" + studentData.module_id;
                    },
                    deleteUrl: function(hash) 
                    {
                        return deleteAnnotationFileUrl +'/' + hash
                        + "?module_id=" + studentData.module_id;
                    },
                    upload_allowed:    true 
                };

                var form = $(element).find("#manage-annotations-form");

                handleUpload(form, fileData);

                form.find("#manage-annotated-exit").on("click", function() {
                    setTimeout(function() {
                        $("#grade-submissions-button").click(); 
                    }, 225);
                });
            }

            /* Click event handler for "enter grade" */
            function handleGradeEntry() 
            {
                var row = $(this).parents("tr");
                var module_id = row.data("module_id")

                var studentData = 
                    $.grep(allStudentData.assignments, function(e){
                        return e.module_id == module_id;
                    })[0];

                var form = $(element).find("#enter-grade-form");
                $(element).find("#student-name").text(studentData.fullname);

                form.find("#module_id-input").val(studentData.module_id);
                form.find("#grade-input").val(studentData.score);
                form.find("#comment-input").text(studentData.comment);

                form.off("submit").on("submit", function(event) {
                    var max_score = allStudentData.max_score;//row.parents("#grade-info").data("max_score");
                    var score = Number(form.find("#grade-input").val());
                    event.preventDefault();

                    if (isNaN(score)) //entered score not integer
                    {
                        form.find(".error").html("<br/>Grade must be a number.");
                    } 
                    else if (score < 0) //entered score not positive
                    {
                        form.find(".error").html("<br/>Grade must be positive.");
                    }
                    else if (score > max_score) //entered score too large.
                    {
                        form.find(".error").html("<br/>Maximum score is " + max_score);
                    }
                    else 
                    {
                        // No errors
                        studentData.score = score;
                        studentData.comment = form.find("#comment-input").text();

                        $.post(enterGradeUrl, form.serialize())
                            .success(function() {
                                renderStaffGrading(allStudentData);
                            });
                    }
                });

                //Remove the grade from the student's assignment.
                form.find("#remove-grade").on("click", function() {
                    var url = removeGradeUrl + "?module_id=" + module_id;
                    $.get(url).success(renderStaffGrading);
                });

                //leave the grading pane.
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
                     * See: https://github.com/mitodl/edx-mfu/issues/13
                     */
                    setTimeout(function() {
                        $("#grade-submissions-button").click(); 
                    }, 225);
                });
            }
        }



        //reset a submission, removing all files and grades.
        function removeSubmission(submission)
        {
            submission.uploaded = [];
            submission.annotated = [];

            reopenSubmission(submission);
            removeGrade(submission);
        }

        //reopen submission for student uploads
        function reopenSubmission(submission)
        {
            submission.submitted = false;
            submission.submitted_on = null;
            submission.may_grade = false;
        }

        //remove a grade from a submission
        function removeGrade(submission)
        {
            submission.score = null;
            submission.comment = '';
            submission.published = false;
            submission.approved = false;
        }

        function handleUpload(parent, state)
        {
            //look into removing
            //var state = data;
            if (typeof state.error === 'undefined')
            {
                state.error = "";
            }

            //var parent = e;
            var fileuploadDiv = parent.find('.upload');
            var filelistDiv = parent.find('.filelist');

            handleFilelist(filelistDiv, state)

/*            var renderFileList = function(element)
            {
                return function(){
                    handleFilelist(element, state);
                };
            }(parent.find('.filelist'));*/

            //renderFileList();
            fileuploadDiv.html(uploadTemplate(state));

            fileuploadDiv.find(".fileupload").fileupload({
                url: state.uploadUrl,
                add: function(e, data)
                {
                    var do_upload = fileuploadDiv.html('');
                    $('<button/>')
                        .text('Upload ' + data.files[0].name)
                        .appendTo(do_upload)
                        .click(function() {
                            do_upload.text("Uploading...");
                            data.submit();
                        });
                },
                progressall: function(e, data) 
                {
                    var percent = parseInt(data.loaded / data.total * 100, 10);
                    fileuploadDiv.text("Uploading... " + percent + "%");
                },
                fail: function(e, data) 
                {
                    var error = "";
                    if (data.jqXHR.status == 413)
                    {
                        state.error = "The file you are trying to upload is too large."
                    }
                    else 
                    {
                        // Suitably vague
                        state.error = "There was an error uploading your file.";

                        console.log("There was an error with file upload.");
                        console.log("event: ", e);
                        console.log("data: ", data);
                    }
                    handleUpload(parent, state);
                },
                done: function(e, data) 
                { 
                    if (data.result.success !== undefined) 
                    {
                        // Actually, this is an error
                        state.error = data.result.success;
                    }
                    else 
                    {
                        // The happy path, no errors
                        state.filelist.push(data.result);
                        state.error = "";
                    }
                    //reset the upload field.
                    handleUpload(parent, state);
                    
                }
            });
        }

        function handleFilelist(fileListDiv, state)
        {
            fileListDiv.html(filelistTemplate(state));

            //attach download url
            //would do this with a template, but I am unsure how
            //to use the downloadUrl function in an underscore.js
            //template.
            fileListDiv.find(".fileDownload").each(function() {
                var pos = $(this).attr('value');
                url = state.downloadUrl(state.filelist[pos].sha1);
                $(this).attr("href", url);
            });

            //bind file delete command to url.
            fileListDiv.find(".fileDelete").on("click", function() {
                var url = state.deleteUrl(state.filelist[this.value].sha1);
                var pos = this.value;

                $.get(url).success(function(data) {
                    if (pos < state.filelist.length)
                    {
                        state.filelist.splice(pos, 1);
                    }

                    handleFilelist(fileListDiv, state)
                });
            });
        }


        $(function($) { // onLoad
            var block = $(element).find(".mfu-block");
            var state = block.attr("data-state");
            render(JSON.parse(state));

            var is_staff = block.attr("data-staff") == "True";
            if (is_staff) {
                gradingTemplate = _.template(
                    $(element).find("#mfu-grading-tmpl").text());

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
    else 
    {
        /**
         * Studio, on the other hand, uses require.js and already knows about
         * jquery.fileupload.
         */
        require(["jquery", "underscore", "jquery.fileupload"], xblock);
    }
}